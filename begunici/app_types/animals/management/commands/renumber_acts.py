"""Chronological monthly numbering per act type; no backups or business audit writes."""

import hashlib
import posixpath
import re
from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO
from xml.etree import ElementTree
from xml.sax.saxutils import escape
from zipfile import ZipFile

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from begunici.app_types.animals.act_numbering import (
    archive_source,
    collect_sources,
    inventory_source,
    is_generated_version,
    lock_registry,
    numbered_excel,
    numbering_context,
    ordered_numbers,
    sync_numbers,
)
from begunici.app_types.animals.models import (
    ARCHIVE_STATUS_NAMES,
    ActNumber,
    ArchiveAct,
    Ewe,
    Maker,
    Ram,
    Sheep,
)
from begunici.app_types.animals.models_user_log import UserActionLog
from begunici.app_types.veterinary.vet_models import StatusHistory
from begunici.app_types.inventory.models import Document, DocumentVersion
from begunici.app_types.feed_inventory.models import FeedDocument, FeedVersion
from begunici.app_types.vet_inventory.models import VetDocument, VetVersion


# These dates were explicitly approved as accounting dates, not actual death dates.
LEGACY_ARCHIVE_DATE = date(2026, 6, 23)
LEGACY_ARCHIVE_STATUSES = {
    "АК352": "Вынужденная прирезка",
    "6163": "Падеж",
    "6254": "Падеж",
    "6260": "Падеж",
    "6267": "Падеж",
    "4859": "Падеж",
}
LEGACY_RESTORED_TAG = "6158"
LEGACY_TAGS = {*LEGACY_ARCHIVE_STATUSES, LEGACY_RESTORED_TAG}
# Reviewed upload; the fingerprint covers every package part except number cell K3.
APPROVED_SP55_FINGERPRINTS = {
    "e1f3eb9b47792ea27272a84fd6b88d8e3cc2e775183332abc7c877b27c0042b3",
}
NUMBER_CELL = re.compile(
    rb'<c\b(?=[^>]*\br="K3")(?P<attrs>[^>]*?)(?:/>|>.*?</c>)', re.DOTALL
)


def archive_repair_plan():
    repairs, excluded, messages = [], set(), []
    for act in ArchiveAct.objects.filter(
        tag__tag_number__in=LEGACY_TAGS,
        act_date__isnull=True,
        status_date__isnull=True,
        act_group_key__isnull=True,
    ).select_related("tag"):
        tag = act.tag.tag_number
        if timezone.localdate(act.created_at) != LEGACY_ARCHIVE_DATE:
            continue
        animals = []
        for model in (Maker, Ram, Ewe, Sheep):
            animals.extend(
                model.objects.filter(tag_id=act.tag_id).values(
                    "is_archived", "animal_status__status_type"
                )
            )
        if len(animals) != 1:
            continue
        animal = animals[0]
        if tag == LEGACY_RESTORED_TAG:
            restoration = (
                UserActionLog.objects.filter(
                    object_id=tag,
                    action_type="Восстановление из архива",
                    timestamp__gt=act.created_at,
                )
                .order_by("timestamp", "pk")
                .first()
            )
            if (
                act.status_name == "Падеж"
                and not animal["is_archived"]
                and animal["animal_status__status_type"] not in ARCHIVE_STATUS_NAMES
                and restoration
            ):
                excluded.add(act.pk)
                messages.append(
                    f"Акт #{act.pk} (бирка {tag}) исключён: животное восстановлено {timezone.localdate(restoration.timestamp):%d.%m.%Y}; история сохраняется"
                )
            continue
        if (
            act.status_name != LEGACY_ARCHIVE_STATUSES[tag]
            or not animal["is_archived"]
            or animal["animal_status__status_type"] != act.status_name
        ):
            continue
        start, end = (
            act.created_at - timedelta(minutes=1),
            act.created_at + timedelta(minutes=1),
        )
        histories = list(
            StatusHistory.objects.filter(
                tag_id=act.tag_id,
                new_status__status_type=act.status_name,
                change_date__range=(start, end),
            )
        )
        logs = list(
            UserActionLog.objects.filter(
                object_id=tag,
                action_type="Архивирование животного",
                timestamp__range=(start, end),
                description__contains=act.status_name,
            )
        )
        if (
            len(histories) != 1
            or not logs
            or timezone.localdate(histories[0].change_date) != LEGACY_ARCHIVE_DATE
            or any(
                timezone.localdate(log.timestamp) != LEGACY_ARCHIVE_DATE for log in logs
            )
        ):
            continue
        repairs.append(act)
        messages.append(
            f"Акт #{act.pk} (бирка {tag}): восстановление учётной даты акта и архивации {LEGACY_ARCHIVE_DATE:%d.%m.%Y}; подтверждено историей статусов и логом"
        )
    return repairs, excluded, messages


def uploaded_sp55_parts(content):
    """Locate the first sheet without reserializing any workbook parts."""
    with ZipFile(BytesIO(content)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(
            name.lower().startswith("_xmlsignatures/") for name in names
        ):
            raise ValueError(
                "Подписанный или неоднозначный Excel нельзя изменять автоматически"
            )
        main_ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        rel_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        first_sheet = workbook.find(f"{main_ns}sheets/{main_ns}sheet")
        relation_id = first_sheet.attrib[f"{rel_ns}id"]
        relations = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(
            item.attrib["Target"]
            for item in relations
            if item.attrib["Id"] == relation_id
        )
        sheet_path = posixpath.normpath(
            target.lstrip("/")
            if target.startswith("/")
            else posixpath.join("xl", target)
        )
        sheet_xml = archive.read(sheet_path)
        matches = list(NUMBER_CELL.finditer(sheet_xml))
        if len(matches) != 1:
            raise ValueError("Ячейка номера СП-55 не найдена однозначно")
        digest = hashlib.sha256()
        for name in sorted(names):
            body = archive.read(name)
            if name == sheet_path:
                body = NUMBER_CELL.sub(b"<ACT_NUMBER/>", body, count=1)
            encoded_name = name.encode("utf-8")
            digest.update(len(encoded_name).to_bytes(8, "big") + encoded_name)
            digest.update(len(body).to_bytes(8, "big") + body)
        return digest.hexdigest(), sheet_path, sheet_xml, matches[0]


def approved_uploaded_sp55(content, number):
    try:
        fingerprint, sheet_path, sheet_xml, cell = uploaded_sp55_parts(content)
    except Exception:
        return None
    if fingerprint not in APPROVED_SP55_FINGERPRINTS:
        return None
    attrs = re.sub(rb'\s+t="[^"]*"', b"", cell.group("attrs"))
    text = escape(f"УЧЕТНЫЙ ЛИСТ № {number}").encode("utf-8")
    replacement = b"<c" + attrs + b' t="inlineStr"><is><t>' + text + b"</t></is></c>"
    if cell.group() == replacement:
        return content
    updated = sheet_xml[: cell.start()] + replacement + sheet_xml[cell.end() :]
    output = BytesIO()
    with ZipFile(BytesIO(content)) as original, ZipFile(output, "w") as result:
        result.comment = original.comment
        for item in original.infolist():
            result.writestr(
                item,
                updated
                if item.filename == sheet_path
                else original.read(item.filename),
            )
    return output.getvalue()


def file_plan(mapping, ignored_archive_ids=()):
    changes, warnings = [], []
    generated_hashes = defaultdict(set)
    converted = {}
    for document_id, digest in DocumentVersion.objects.filter(
        origin="generated"
    ).values_list("document_id", "sha256"):
        generated_hashes[document_id].add(digest)
    for act in ArchiveAct.objects.filter(
        status_name__in=ARCHIVE_STATUS_NAMES,
        act_date__isnull=True,
        status_date__isnull=True,
    ).exclude(pk__in=ignored_archive_ids):
        if not archive_source(act).date:
            warnings.append(
                f"Архивный акт #{act.pk} (бирка {act.tag.tag_number}): нет даты акта/архивации; номер не присвоен"
            )
    for version in DocumentVersion.objects.filter(
        document__kind__in=["sp54", "sp55"]
    ).select_related("document"):
        spec = inventory_source(version.document)
        number = mapping.get(spec.identity)
        if not number:
            warnings.append(
                f"Складской акт #{version.document_id}: нет достоверной даты; номер не присвоен"
            )
            continue
        content = bytes(version.content)
        if hashlib.sha256(content).hexdigest() != version.sha256:
            raise ValueError(f"Файл {version.pk}: контрольная сумма не совпадает")
        if not version.filename.lower().endswith(".xlsx"):
            warnings.append(
                f"{version.document_id}, версия {version.number}: номер {number}; PDF/внешний файл не изменён"
            )
            continue
        if not is_generated_version(version, generated_hashes[version.document_id]):
            updated = (
                approved_uploaded_sp55(content, number)
                if version.document.kind == "sp55"
                else None
            )
            if updated is not None:
                if updated != content:
                    changes.append((version, updated))
                continue
            warnings.append(
                f"{version.document_id}, версия {version.number}: внешний файл не изменён; номер {number} надо внести вручную"
            )
            continue
        key = (version.sha256, number, version.document.kind)
        if key not in converted:
            converted[key] = numbered_excel(
                content,
                number,
                "sp55" if version.document.kind == "sp55" else "archive",
            )
        updated = converted[key]
        if updated is None:
            warnings.append(
                f"{version.document_id}, версия {version.number}: форма не распознана; номер {number} надо внести вручную"
            )
        elif updated != content:
            changes.append((version, updated))
    for model in (FeedVersion, VetVersion):
        for version in (
            model.objects.filter(document__kind="writeoff")
            .exclude(filename="")
            .select_related("document")
        ):
            kind = "feed_writeoff" if model is FeedVersion else "vet_writeoff"
            number = mapping.get((kind, str(version.document_id)))
            if number:
                warnings.append(
                    f"{kind} #{version.document_id}, версия {version.number}: внешний файл не изменён; номер {number}"
                )
    return changes, warnings


def renumber(*, apply=False, emit=print):
    with transaction.atomic():
        if apply:
            # Keep the same document-before-registry lock order as normal editing.
            for model in (ArchiveAct, Document, FeedDocument, VetDocument):
                list(
                    model.objects.select_for_update(nowait=True)
                    .order_by("pk")
                    .values_list("pk", flat=True)
                )
            # Fail rather than deadlock if an archive edit already owns the registry.
            lock_registry(wait=False)
            for model in (Maker, Ram, Ewe, Sheep):
                list(
                    model.objects.filter(tag__tag_number__in=LEGACY_TAGS)
                    .select_for_update(nowait=True, of=("self",))
                    .values_list("pk", flat=True)
                )
        repairs, excluded, messages = archive_repair_plan()
        sources = collect_sources()
        for act in repairs:
            act.act_date = act.status_date = LEGACY_ARCHIVE_DATE
            spec = archive_source(act)
            sources[spec.identity] = spec
        planned = ordered_numbers(sources)
        mapping = {
            identity: f"{sequence}_{spec.date:%m%y}"
            for identity, (spec, sequence) in planned.items()
        }
        changes, warnings = file_plan(
            mapping, ignored_archive_ids=excluded | {act.pk for act in repairs}
        )
        for message in messages:
            emit(message)
        for identity, (spec, _) in planned.items():
            emit(
                f"{spec.date:%d.%m.%Y} | {spec.kind} | {spec.key} -> {mapping[identity]}"
            )
        for warning in warnings:
            emit("Внимание: " + warning)
        emit(
            f"Актов: {len(planned)}; Excel-файлов к обновлению: {len(changes)}; предупреждений: {len(warnings)}"
        )
        if not apply:
            emit(
                "Только проверка. Для записи используйте --apply. Бэкапы и логи не создаются"
            )
            return {"acts": len(planned), "files": len(changes), "warnings": warnings}
        for act in repairs:
            updated = ArchiveAct.objects.filter(
                pk=act.pk,
                tag__tag_number=act.tag.tag_number,
                status_name=act.status_name,
                act_date__isnull=True,
                status_date__isnull=True,
            ).update(act_date=LEGACY_ARCHIVE_DATE, status_date=LEGACY_ARCHIVE_DATE)
            if updated != 1:
                raise ValueError(
                    f"Акт #{act.pk} изменился во время восстановления даты"
                )
        registry = sync_numbers()
        actual = {identity: row.number for identity, row in registry.items()}
        if any(actual.get(key) != value for key, value in mapping.items()):
            raise ValueError(
                "Набор актов изменился во время проверки. Повторите команду"
            )
        legacy_updates = {}

        def remember_number(identity, legacy):
            row = registry.get(identity)
            if (
                row
                and legacy
                and legacy != row.number
                and legacy not in row.legacy_numbers
            ):
                row.legacy_numbers = [*row.legacy_numbers, legacy]
                legacy_updates[row.pk] = row

        with numbering_context(registry):
            for act in ArchiveAct.objects.all():
                if act.pk in excluded:
                    continue
                identity = archive_source(act).identity
                number = actual.get(identity)
                if number:
                    remember_number(identity, act.act_number)
                    ArchiveAct.objects.filter(pk=act.pk).update(act_number=number)
            for document in Document.objects.filter(kind__in=["sp54", "sp55"]):
                identity = inventory_source(document).identity
                number = actual.get(identity)
                if number:
                    remember_number(identity, document.number)
                    Document.objects.filter(pk=document.pk).update(number=number)
            for kind, model in (
                ("feed_writeoff", FeedDocument),
                ("vet_writeoff", VetDocument),
            ):
                for document in model.objects.filter(kind="writeoff"):
                    number = actual.get((kind, str(document.pk)))
                    if number:
                        remember_number((kind, str(document.pk)), document.number)
                        model.objects.filter(pk=document.pk).update(number=number)
            if legacy_updates:
                ActNumber.objects.bulk_update(
                    list(legacy_updates.values()), ["legacy_numbers"]
                )
            # Authorized maintenance update: version IDs, snapshots and all ledger rows stay intact.
            table = connection.ops.quote_name(DocumentVersion._meta.db_table)
            with connection.cursor() as cursor:
                for version, content in changes:
                    cursor.execute(
                        f"UPDATE {table} SET content=%s, sha256=%s WHERE id=%s AND sha256=%s",
                        [
                            content,
                            hashlib.sha256(content).hexdigest(),
                            version.pk,
                            version.sha256,
                        ],
                    )
                    if cursor.rowcount != 1:
                        raise ValueError(
                            f"Версия {version.pk} изменилась во время обновления"
                        )
        emit(
            "Нумерация и подтверждённые даты актов обновлены. Статусы животных, веса, суммы и складские остатки не изменены"
        )
        return {"acts": len(planned), "files": len(changes), "warnings": warnings}


class Command(BaseCommand):
    help = "Нумерация N_MMYY отдельно для каждого вида актов, с 1 каждый месяц; без --apply только проверка"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Записать номера и обновить распознанные Excel-файлы",
        )

    def handle(self, *args, **options):
        try:
            renumber(apply=options["apply"], emit=self.stdout.write)
        except Exception as exc:
            raise CommandError(f"Перенумерация отменена: {exc}") from exc
