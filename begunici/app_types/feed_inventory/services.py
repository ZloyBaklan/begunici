"""Only explicit, authorized commands can change feed stock; no signals or timers."""
import hashlib
import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from begunici.app_types.animals.feed_plan import FEED_GROUP_LABELS
from begunici.app_types.inventory.documents import read_upload
from begunici.app_types.inventory.permissions import require_inventory
from begunici.app_types.inventory.validation import amount
from .models import FeedAudit, FeedDocument, FeedMovement, FeedNorm, FeedOrder, FeedProduct, FeedSettings, FeedVersion
from .plan import build_plan, number

WRITEOFF_REASONS = [
    ("moisture", "Отсыревание"), ("spoilage", "Порча / непригодность"),
    ("bedding", "Передача на подстилку"), ("other", "Другая причина"),
]


def writeoff_reason(value):
    if value not in dict(WRITEOFF_REASONS):
        raise ValidationError("Выберите причину списания.")
    return {"reason": value, "reason_label": dict(WRITEOFF_REASONS)[value]}


def product_restrictions(product):
    # JSON snapshots intentionally stay independent of mutable catalog names.
    # Iteration also supports the existing SQLite preview; JSON containment is
    # PostgreSQL-only. Read just the line arrays, never attached binary files.
    used = product.movements.exists()
    if not used:
        for collection in (FeedOrder.objects.values_list("lines", flat=True),
                           FeedVersion.objects.values_list("payload__lines", flat=True)):
            if any(any(row.get("product") == product.pk for row in (lines or [])) for lines in collection.iterator()):
                used = True
                break
    return {"unit_locked": used or product.norms.filter(per_head__gt=0).exists(), "package_locked": used}


def product_name_exists(name, exclude_pk=None):
    products = FeedProduct.objects.all()
    if exclude_pk is not None:
        products = products.exclude(pk=exclude_pk)
    # SQLite's ILIKE/NOCASE does not fold Cyrillic; use the same comparison on
    # both preview and PostgreSQL. Callers hold the catalog/accounting lock.
    return any(existing.casefold() == name.casefold() for existing in products.values_list("name", flat=True))


@transaction.atomic
def update_product(user, pk, revision, name, category, unit, package):
    config = lock(user)
    product = FeedProduct.objects.select_for_update().get(pk=pk)
    if str(product.revision) != str(revision):
        raise ValidationError("Номенклатура уже изменена. Обновите страницу перед редактированием.")
    if category not in dict(FeedProduct._meta.get_field("category").choices) or unit not in dict(FeedProduct._meta.get_field("unit").choices):
        raise ValidationError("Выберите категорию и единицу измерения из списка.")
    name, package = text(name, "Название", 120), text(package, "Упаковка", 40, False)
    if product_name_exists(name, exclude_pk=pk):
        raise ValidationError("Такая номенклатура уже существует.")
    restrictions = product_restrictions(product)
    if restrictions["unit_locked"] and product.unit != unit:
        raise ValidationError("Единица уже используется в документах или нормах. Для другой единицы создайте отдельную номенклатуру.")
    if restrictions["package_locked"] and product.package != package:
        raise ValidationError("Упаковка уже используется в документах. Для другого вида упаковки создайте отдельную номенклатуру.")
    before = {"name": product.name, "category": product.get_category_display(),
              "unit": product.get_unit_display(), "package": product.package}
    product.name, product.category, product.unit, product.package = name, category, unit, package
    product.revision += 1
    product.save(update_fields=["name", "category", "unit", "package", "revision"])
    config.revision += 1
    config.save(update_fields=["revision"])
    audit(user, "Изменена номенклатура", product=product.pk, before=before,
          after={"name": product.name, "category": product.get_category_display(),
                 "unit": product.get_unit_display(), "package": product.package})
    return product


def lock(user):
    require_inventory(user)
    return FeedSettings.objects.select_for_update().get(pk=1)


def audit(user, action, **data):
    FeedAudit.objects.create(created_by=user, action=action, data=data)


def token(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        raise ValidationError("Обновите страницу перед сохранением.")


def text(value, label, max_length, required=True):
    value = str(value or "").strip()
    if (required and not value) or len(value) > max_length:
        raise ValidationError(f"{label}: заполните поле (до {max_length} символов).")
    return value


def valid_date(value):
    try:
        result = date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError("Укажите дату документа.")
    if result > timezone.localdate():
        raise ValidationError("Приход и фактический расход нельзя оформлять будущей датой.")
    return result


def normalize_lines(rows, allow_empty=False):
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValidationError("Допускается не более 200 позиций.")
    result, used = [], set()
    products = {p.pk: p for p in FeedProduct.objects.all()}
    for row in rows:
        try:
            product = products[int(row["product"])]
        except (KeyError, ValueError, TypeError):
            raise ValidationError("Номенклатура не найдена.")
        if product.pk in used:
            raise ValidationError("Объедините повторяющиеся позиции корма в одну строку.")
        used.add(product.pk)
        quantity = amount(row.get("amount") or 0, "Количество", allow_zero=True)
        packages = amount(row.get("packages") or 0, "Упаковки", allow_zero=True)
        if quantity == 0 and packages == 0:
            continue
        if quantity == 0:
            raise ValidationError(f"{product.name}: укажите количество в {product.get_unit_display()}.")
        if packages and not product.package:
            raise ValidationError(f"{product.name}: для этой позиции упаковки не учитываются.")
        result.append({"product": product.pk, "name": product.name, "unit": product.get_unit_display(),
                       "package": product.package, "amount": number(quantity), "packages": number(packages)})
    if not result and not allow_empty:
        raise ValidationError("Добавьте хотя бы одну позицию с положительным количеством.")
    return result


def balances():
    return {row["product_id"]: (row["amount"] or Decimal(0), row["packages"] or Decimal(0))
            for row in FeedMovement.objects.values("product_id").annotate(amount=Sum("amount"), packages=Sum("packages"))}


def stock_rows(plan=None):
    plan = plan or build_plan()
    stock = balances()
    rows = []
    for product in plan["products"]:
        available, packages = stock.get(product["id"], (Decimal(0), Decimal(0)))
        daily = Decimal(product["daily"])
        rows.append({**product, "available": available, "packages": packages,
                     "days_left": number((available / daily).quantize(Decimal("0.1"))) if daily else "—",
                     "shortage": daily > available})
    return rows


def order_progress(order):
    received = {r["product_id"]: r for r in FeedMovement.objects.filter(document__order=order)
                .values("product_id").annotate(amount=Sum("amount"), packages=Sum("packages"))}
    rows, any_received, complete = [], False, True
    for line in order.lines:
        totals = received.get(line["product"], {})
        delivered = totals.get("amount", Decimal(0))
        packs = totals.get("packages", Decimal(0))
        missing = max(Decimal(line["amount"]) - delivered, Decimal(0))
        missing_packs = max(Decimal(line["packages"]) - packs, Decimal(0))
        covered = missing == 0 and missing_packs == 0
        complete = complete and covered
        any_received = any_received or delivered > 0 or packs > 0
        rows.append({**line, "received": delivered, "received_packages": packs,
                     "missing": missing, "missing_packages": missing_packs, "covered": covered})
    return {"rows": rows, "complete": complete, "partial": any_received and not complete,
            "label": "Выполнена" if complete else "Частично выполнена" if any_received else "Ожидает прихода"}


@transaction.atomic
def create_product(user, name, category, unit, package):
    lock(user)
    if category not in dict(FeedProduct._meta.get_field("category").choices) or unit not in dict(FeedProduct._meta.get_field("unit").choices):
        raise ValidationError("Выберите категорию и единицу измерения из списка.")
    name = text(name, "Название", 120)
    if product_name_exists(name):
        raise ValidationError("Такая номенклатура уже существует.")
    product = FeedProduct.objects.create(name=name, category=category, unit=unit, package=text(package, "Упаковка", 40, False))
    FeedNorm.objects.bulk_create([FeedNorm(product=product, group=g) for g in FEED_GROUP_LABELS])
    config = FeedSettings.objects.get(pk=1)
    config.revision += 1
    config.save(update_fields=["revision"])
    audit(user, "Добавлена номенклатура", product=product.pk, name=product.name, unit=unit, package=product.package)
    return product


@transaction.atomic
def save_norms(user, revision, values):
    config = lock(user)
    if str(revision) != str(config.revision):
        raise ValidationError("Нормы уже изменены другим пользователем. Обновите страницу.")
    changes = []
    for norm in FeedNorm.objects.select_related("product"):
        key = f"norm_{norm.product_id}_{norm.group}"
        if key not in values:
            raise ValidationError("Получены не все нормы. Обновите страницу.")
        raw = str(values[key]).strip()
        value = None if raw == "" else amount(raw, "Норма", allow_zero=True)
        if value != norm.per_head:
            changes.append({"product": norm.product_id, "name": norm.product.name,
                            "group": norm.group, "label": FEED_GROUP_LABELS[norm.group],
                            "before": None if norm.per_head is None else str(norm.per_head),
                            "after": None if value is None else str(value)})
            norm.per_head = value
            norm.save(update_fields=["per_head"])
    config.revision += 1
    config.save(update_fields=["revision"])
    audit(user, "Изменены нормы потребления", revision=config.revision, changes=changes)


@transaction.atomic
def create_order(user, supplier, note, lines, request_token):
    lock(user)
    request_token = token(request_token)
    existing = FeedOrder.objects.filter(token=request_token).first()
    if existing:
        return existing
    order = FeedOrder.objects.create(created_by=user, supplier=text(supplier, "Поставщик", 200),
                                     note=text(note, "Примечание", 4000, False),
                                     lines=normalize_lines(lines), token=request_token)
    audit(user, "Создана заявка на приход", order=order.pk)
    return order


def add_version(document, user, payload, upload=None, previous=None):
    data = {"filename": "", "content": b"", "content_type": "", "sha256": ""}
    if previous:
        data = {key: getattr(previous, key) for key in data}
    if upload:
        content, filename, content_type = read_upload(upload)
        data = {"filename": filename, "content": content, "content_type": content_type,
                "sha256": hashlib.sha256(content).hexdigest()}
    return FeedVersion.objects.create(document=document, number=document.revision,
                                      created_by=user, payload=payload, **data)


@transaction.atomic
def create_document(user, kind, document_date, number_, lines, note, request_token, order_id=None, upload=None, reason=None):
    lock(user)
    if kind not in {"receipt", "consume", "writeoff"}:
        raise ValidationError("Неизвестный вид документа.")
    request_token = token(request_token)
    existing = FeedDocument.objects.filter(token=request_token).first()
    if existing:
        return existing
    order = None
    if kind == "receipt":
        order = FeedOrder.objects.filter(pk=order_id).first()
        if not order:
            raise ValidationError("Приходная накладная создаётся из входящей заявки.")
    clean_lines = normalize_lines(lines)
    if order and any(line["product"] not in {r["product"] for r in order.lines} for line in clean_lines):
        raise ValidationError("В накладной есть корм, не указанный в заявке. Создайте для него заявку.")
    document = FeedDocument.objects.create(kind=kind, date=valid_date(document_date), order=order,
        number=text(number_, "Номер накладной", 100, kind == "receipt"), token=request_token, created_by=user)
    payload = {"lines": clean_lines, "note": text(note, "Примечание", 4000, False)}
    if kind == "writeoff":
        payload.update(writeoff_reason(reason))
        payload["note"] = text(note, "Обоснование списания", 4000)
    if kind == "consume":
        # Snapshot is captured with creation, not reconstructed when confirming.
        payload["plan"] = build_plan()
    add_version(document, user, payload, upload)
    audit(user, "Создан черновик", document=document.pk)
    return document


def checked_document(pk, revision):
    document = FeedDocument.objects.select_for_update().get(pk=pk)
    if str(document.revision) != str(revision):
        raise ValidationError("Документ изменился. Обновите страницу и проверьте новую версию.")
    return document


@transaction.atomic
def edit_draft(user, pk, revision, lines, note, upload=None, replace_confirmed=False, reason=None):
    lock(user)
    document = checked_document(pk, revision)
    if document.state != "draft":
        raise ValidationError("Изменять можно только черновик. Для подтверждённого документа используйте сторно.")
    previous = document.versions.first()
    if upload and previous.filename and not replace_confirmed:
        raise ValidationError("Подтвердите замену вложения. Предыдущая версия останется в истории.")
    clean_lines = normalize_lines(lines)
    if document.order_id and any(line["product"] not in {r["product"] for r in document.order.lines} for line in clean_lines):
        raise ValidationError("Позиция отсутствует в заявке.")
    payload = {**previous.payload, "lines": clean_lines, "note": text(note, "Примечание", 4000, False)}
    if document.kind == "writeoff":
        payload.update(writeoff_reason(reason if reason is not None else previous.payload.get("reason")))
        payload["note"] = text(note, "Обоснование списания", 4000)
        if previous.filename and not upload and payload != previous.payload:
            raise ValidationError("Состав или причина списания изменились. Приложите исправленный акт; старый останется в истории.")
    document.revision += 1
    document.save(update_fields=["revision"])
    add_version(document, user, payload, upload, previous)
    audit(user, "Исправлен черновик", document=document.pk, revision=document.revision)
    return document


@transaction.atomic
def confirm_document(user, pk, revision):
    lock(user)
    document = checked_document(pk, revision)
    if document.state == "posted":
        return document  # A repeated confirmation never doubles the ledger.
    if document.state != "draft":
        raise ValidationError("Этот документ уже отменён или сторнирован.")
    if document.kind == "consume" and FeedDocument.objects.filter(kind="consume", state="posted", date=document.date).exists():
        raise ValidationError("Расход за эту дату уже подтверждён. Исправление: сторнируйте ошибочный документ и создайте новый.")
    version = document.versions.first()
    if document.kind == "writeoff":
        writeoff_reason(version.payload.get("reason"))
        text(version.payload.get("note"), "Обоснование списания", 4000)
        if not version.filename or not version.content:
            raise ValidationError("Для списания прикрепите подтверждающий акт (PDF или XLSX).")
    sign = 1 if document.kind == "receipt" else -1
    apply_movements(document, version.payload["lines"], sign)
    document.state, document.posted_at, document.posted_by = "posted", timezone.now(), user
    document.save(update_fields=["state", "posted_at", "posted_by"])
    action = {"receipt": "Подтверждён приход", "consume": "Подтверждён расход", "writeoff": "Подтверждено списание по акту"}[document.kind]
    audit(user, action, document=document.pk, revision=document.revision)
    return document


def apply_movements(document, lines, sign):
    current = balances()
    for line in lines:
        quantity, packages = Decimal(line["amount"]) * sign, Decimal(line["packages"]) * sign
        old_quantity, old_packages = current.get(line["product"], (Decimal(0), Decimal(0)))
        if old_quantity + quantity < 0 or old_packages + packages < 0:
            raise ValidationError(f"{line['name']}: недостаточно остатков. Доступно {number(old_quantity)} {line['unit']}, упаковок {number(old_packages)}.")
        FeedMovement.objects.create(document=document, product_id=line["product"], amount=quantity, packages=packages)


@transaction.atomic
def cancel_draft(user, pk, revision):
    lock(user)
    document = checked_document(pk, revision)
    if document.state != "draft":
        raise ValidationError("Отменить можно только черновик.")
    document.state = "cancelled"
    document.save(update_fields=["state"])
    audit(user, "Отменён черновик", document=document.pk)


@transaction.atomic
def reverse_document(user, pk, reason):
    lock(user)
    document = FeedDocument.objects.select_for_update().get(pk=pk)
    reason = text(reason, "Причина сторно", 2000)
    if document.state != "posted" or document.kind == "reversal":
        raise ValidationError("Сторно доступно для подтверждённого прихода или расхода.")
    reversal = FeedDocument.objects.create(kind="reversal", order=document.order, reversal_of=document,
                                           created_by=user, posted_by=user, posted_at=timezone.now(), state="posted")
    lines = document.versions.first().payload["lines"]
    add_version(reversal, user, {"lines": lines, "note": reason})
    apply_movements(reversal, lines, -1 if document.kind == "receipt" else 1)
    document.state = "reversed"
    document.save(update_fields=["state"])
    audit(user, "Сторно", document=document.pk, reversal=reversal.pk, reason=reason)
    return reversal
