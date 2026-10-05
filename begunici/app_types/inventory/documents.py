import hashlib
from io import BytesIO
from pathlib import PurePath
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError

from .bridges import plain
from .models import AuditEvent, DocumentVersion

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_UPLOAD = 10 * 1024 * 1024


def assert_revision(document, expected):
    try:
        current = int(expected)
    except (TypeError, ValueError):
        raise ValidationError("Обновите страницу: не передан номер версии документа.")
    if current != document.revision:
        raise ValidationError("Документ уже изменён другим сотрудником. Обновите страницу и проверьте новую версию.")


def assert_editable(document):
    if document.state in {"confirmed", "reversed"}:
        raise ValidationError("Утверждённый документ неизменяем. Для допродажи создайте дополнительную накладную, для исправления — сторно.")


def read_upload(upload):
    if upload.size > MAX_UPLOAD:
        raise ValidationError("Размер документа не должен превышать 10 МБ.")
    data = upload.read(MAX_UPLOAD + 1)
    filename = str(upload.name).replace("\\", "/").rsplit("/", 1)[-1][:180]
    suffix = PurePath(filename).suffix.lower()
    if len(data) > MAX_UPLOAD or not data:
        raise ValidationError("Пустой или слишком большой документ.")
    if suffix == ".pdf" and data.startswith(b"%PDF-"):
        return data, filename, "application/pdf"
    if suffix == ".xlsx":
        try:
            with ZipFile(BytesIO(data)) as archive:
                names = archive.namelist()
                if len(names) > 3000 or sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
                    raise ValidationError("Слишком большой распакованный Excel-документ.")
                if "xl/workbook.xml" in names and "[Content_Types].xml" in names and not any("vbaproject" in n.lower() for n in names):
                    return data, filename, XLSX_TYPE
        except BadZipFile:
            pass
    raise ValidationError("Поддерживаются настоящие PDF и XLSX без макросов.")


def add_version(document, user, *, content=None, upload=None, reason="", replace_confirmed=False):
    """Caller holds a document lock inside a transaction; files share its commit."""
    assert_editable(document)
    if upload is not None:
        if not replace_confirmed:
            raise ValidationError("Подтвердите замену текущего файла. Предыдущая версия будет сохранена.")
        if not reason.strip():
            raise ValidationError("Укажите причину замены документа.")
        content, filename, content_type = read_upload(upload)
        origin = "uploaded"
    else:
        if content is None:
            from .exports import generate_document
            content = generate_document(document)
        filename = f"{document.kind}_{document.pk}_v{document.revision + 1}.xlsx"
        content_type, origin = XLSX_TYPE, "generated"
    document.revision += 1
    snapshot = plain({
        "kind": document.kind, "number": document.number, "date": document.date,
        "order_id": document.order_id, "payload": document.payload,
        "animals": list(document.animals.values("id", "source_tag_id", "snapshot")),
    })
    version = DocumentVersion.objects.create(
        document=document, number=document.revision, content=content, filename=filename,
        content_type=content_type, sha256=hashlib.sha256(content).hexdigest(),
        snapshot=snapshot, origin=origin, reason=reason.strip(), created_by=user,
    )
    document.save()
    AuditEvent.objects.create(document=document, actor=user, action="version_created", data={
        "version": version.number, "sha256": version.sha256, "reason": reason.strip(), "origin": origin,
    })
    return version
