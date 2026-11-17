from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from begunici.app_types.veterinary.vet_models import Veterinary
from begunici.app_types.inventory.validation import amount
from .models import VetDocument, VetProduct, VetSettings, VetTreatment
from .permissions import require_treat
from .rules import estimate, estimate_product, is_shearing
from .services import add_version, apply_movements, audit, normalize_lines, number, text, resolve_group_expenses


SHEARING_NO_EXPENSE = "Стрижка не требует расхода ветпрепаратов"


def requires_stock(entry, source=None):
    if source is None:
        source = Veterinary.objects.select_related("veterinary_care").filter(pk=entry.source_id).first()
    if source and source.veterinary_care:
        return not is_shearing(source.veterinary_care)
    label = str(entry.snapshot.get("care") or "").rsplit(":", 1)[-1].strip().casefold()
    return label != "стрижка"


def mark_shearing_without_expense(entry):
    entry.state, entry.issue, entry.manual = "excluded", SHEARING_NO_EXPENSE, False
    entry.product, entry.quantity, entry.calculation = None, 0, {"mode_label": "Без расхода", "quantity": "0"}


def snapshot(source):
    care = source.veterinary_care
    return {"tag_id": source.tag_id, "tag": source.tag.tag_number, "care_id": source.veterinary_care_id,
            "care": str(care) if care else "Обработка удалена из справочника",
            "medication": care.medication if care else "", "date": source.get_care_date().isoformat(),
            "date_time": source.date_of_care.isoformat()}


def undo_expense(entry, user, reason):
    document = entry.document
    if document and document.state == "posted":
        reversal = VetDocument.objects.create(kind="reversal", reversal_of=document,
            state="posted", created_by=user, posted_by=user, posted_at=timezone.now())
        lines = document.versions.first().payload["lines"]
        add_version(reversal, user, {"lines": lines, "note": reason, "treatment_id": entry.pk})
        apply_movements(reversal, lines, 1)
        document.state = "reversed"
        document.save(update_fields=["state"])
        audit(user, "Сторно расхода обработки", treatment=entry.pk, document=document.pk, reversal=reversal.pk, reason=reason, animal=entry.snapshot)
    entry.document = None


def post_expense(entry, user, reason):
    from datetime import date
    if not requires_stock(entry):
        raise ValidationError(SHEARING_NO_EXPENSE)
    if date.fromisoformat(entry.snapshot["date"]) > timezone.localdate():
        raise ValidationError("Обработка датирована будущим числом. Проверьте дату перед списанием.")
    selection = entry.calculation.get("group_expenses", [])
    if selection and "expense_lines" not in entry.calculation:
        # Allocate only after any previous expense has been reversed, under the ledger lock.
        if all(Decimal(row["amount"]) == 0 for row in selection):
            lines = []
        else:
            lines, selection = resolve_group_expenses(selection, decimal_places=18)
        entry.product_id = lines[0]["product"] if len(lines) == 1 else None
        entry.quantity = Decimal(lines[0]["amount"]) if len(lines) == 1 else None
        entry.calculation.update(group_expenses=selection, expense_lines=lines)
    lines = entry.calculation["expense_lines"] if selection else normalize_lines(
        [{"product": entry.product_id, "amount": number(entry.quantity), "packages": "0"}], allow_empty=True)
    doc = VetDocument.objects.create(kind="treatment", date=entry.snapshot["date"], state="posted",
        created_by=user, posted_by=user, posted_at=timezone.now())
    add_version(doc, user, {"lines": lines, "note": reason, "treatment_id": entry.pk,
                            "animal": entry.snapshot, "calculation": entry.calculation, "manual": entry.manual,
                            **({"group_expenses": selection} if selection else {})})
    apply_movements(doc, lines, -1)
    entry.document, entry.state, entry.issue = doc, "posted", ""
    audit(user, "Учтён расход обработки", treatment=entry.pk, document=doc.pk,
          quantity=selection[0]["amount"] if selection else number(entry.quantity),
          unit=selection[0]["unit_label"] if selection else entry.product.get_unit_display(),
          manual=entry.manual, reason=reason, animal=entry.snapshot)


@transaction.atomic
def capture(source_id, user=None, created=False):
    config = VetSettings.objects.select_for_update().filter(pk=1).first()
    if not config:
        return  # The app is not migrated yet.
    source = Veterinary.objects.select_related("tag", "veterinary_care").filter(pk=source_id).first()
    if source is None:
        return
    entry = VetTreatment.objects.select_for_update().filter(source_id=source_id).first()
    shearing = is_shearing(source.veterinary_care)
    if entry is None and (not created or source_id <= config.legacy_treatment_id):
        return  # Historical treatments are never charged retrospectively.
    current = snapshot(source)
    if entry:
        if all(entry.snapshot.get(key) == current.get(key) for key in ("tag_id", "care_id", "date_time")):
            if shearing and entry.state == "pending" and entry.document_id is None:
                mark_shearing_without_expense(entry)
                entry.revision += 1
                entry.save()
            return  # Comments, hiding and repeated saves do not alter consumption.
        undo_expense(entry, user, "Изменены животное, обработка или дата исходного мероприятия")
        entry.revision += 1
    else:
        entry = VetTreatment.objects.create(source_id=source_id, snapshot=current)
    entry.snapshot, entry.state, entry.issue = current, "pending", ""
    if shearing:
        mark_shearing_without_expense(entry)
        entry.save()
        audit(user, "Обработка без расхода", treatment=entry.pk, reason=SHEARING_NO_EXPENSE, animal=entry.snapshot)
        return entry
    try:
        if entry.manual:
            raise ValidationError("Данные мероприятия изменились после ручного уточнения. Проверьте расход повторно.")
        entry.product, entry.quantity, entry.calculation = None, None, {}
        entry.product, entry.quantity, entry.calculation = estimate_product(source)
        # A shortage rolls back only the attempted movement, preserving the queue.
        with transaction.atomic():
            post_expense(entry, user, "Приблизительный расход по норме на момент обработки")
    except ValidationError as exc:
        entry.issue = "; ".join(exc.messages)
        entry.document, entry.state = None, "pending"
        audit(user, "Расход требует сверки", treatment=entry.pk, reason=entry.issue, animal=entry.snapshot)
    entry.save()
    return entry


@transaction.atomic
def adjust(user, pk, revision, product_id, quantity, reason, recalculate=False, weight=None, group_expenses=None, direct=False):
    require_treat(user)
    VetSettings.objects.select_for_update().get(pk=1)
    entry = VetTreatment.objects.select_for_update().get(pk=pk)
    if str(entry.revision) != str(revision):
        raise ValidationError("Расход уже изменён. Обновите страницу.")
    if entry.state == "deleted":
        raise ValidationError("Исходная обработка удалена; расход отменён.")
    if not requires_stock(entry):
        raise ValidationError(SHEARING_NO_EXPENSE)
    reason = text(reason, "Причина уточнения", 2000)
    if direct:
        has_quantity = bool(str(quantity if quantity is not None else "").strip())
        try:
            product = VetProduct.objects.get(pk=product_id)
        except (VetProduct.DoesNotExist, TypeError, ValueError):
            raise ValidationError("Выберите конкретный препарат.")
        source = Veterinary.objects.select_related("tag", "veterinary_care").filter(pk=entry.source_id).first()
        expected, calculation = None, {}
        try:
            if source is None:
                raise ValidationError("Исходная обработка недоступна для расчёта.")
            _, expected, calculation = estimate_product(source, product_id=product.pk, weight=weight)
        except ValidationError:
            if recalculate or not has_quantity:
                raise
        actual = expected if recalculate or not has_quantity else amount(quantity, "Фактический расход", allow_zero=True)
        entry.product, entry.quantity = product, actual
        entry.manual = expected is None or actual != expected
        entry.calculation = {**calculation, "quantity": number(actual)}
        if expected is not None:
            entry.calculation["expected_quantity"] = number(expected)
        if entry.manual:
            entry.calculation["mode_label"] = "Уточнено вручную"
        if source:
            entry.snapshot = snapshot(source)
        undo_expense(entry, user, reason)
        post_expense(entry, user, reason)
        entry.revision += 1
        entry.save()
        return entry
    if group_expenses is not None:
        if recalculate or len(group_expenses) != 1:
            raise ValidationError("Для уточнения обработки выберите одну группу препарата.")
        undo_expense(entry, user, reason)
        lines, selections = resolve_group_expenses(group_expenses)
        entry.product_id = lines[0]["product"] if len(lines) == 1 else None
        entry.quantity = Decimal(lines[0]["amount"]) if len(lines) == 1 else None
        entry.calculation = {"group_expenses": selections, "expense_lines": lines, "mode_label": "Уточнено вручную"}
        entry.manual = True
        post_expense(entry, user, reason)
        entry.revision += 1
        entry.save()
        return entry
    if recalculate:
        source = Veterinary.objects.select_related("tag", "veterinary_care").filter(pk=entry.source_id).first()
        if source is None:
            raise ValidationError("Исходная обработка недоступна для пересчёта.")
        entry.product, entry.quantity, entry.calculation = estimate(source, weight=weight)
        entry.snapshot = snapshot(source)
        entry.manual = False
    else:
        try:
            entry.product = VetProduct.objects.filter(pk=product_id).first()
        except (ValueError, TypeError):
            entry.product = None
        if not entry.product:
            raise ValidationError("Выберите препарат.")
        entry.quantity = amount(quantity, "Фактический расход", allow_zero=True)
        entry.calculation = {"quantity": number(entry.quantity), "mode_label": "Уточнено вручную"}
        entry.manual = True
    undo_expense(entry, user, reason)
    post_expense(entry, user, reason)
    entry.revision += 1
    entry.save()
    return entry


@transaction.atomic
def exclude(user, pk, revision, reason):
    require_treat(user)
    VetSettings.objects.select_for_update().get(pk=1)
    entry = VetTreatment.objects.select_for_update().get(pk=pk)
    if str(entry.revision) != str(revision) or entry.state == "deleted":
        raise ValidationError("Расход изменён или обработка удалена. Обновите страницу.")
    reason = text(reason, "Причина отсутствия расхода", 2000)
    undo_expense(entry, user, reason)
    entry.state, entry.issue, entry.manual = "excluded", reason, True
    entry.revision += 1
    entry.save()
    audit(user, "Обработка без расхода", treatment=entry.pk, reason=reason, animal=entry.snapshot)


@transaction.atomic
def deleted(source_id, user=None, cascade=False):
    if not VetSettings.objects.select_for_update().filter(pk=1).exists():
        return
    entry = VetTreatment.objects.select_for_update().filter(source_id=source_id).first()
    if not entry:
        return
    if cascade:
        # Deleting an animal does not mean the medicine was returned to storage.
        audit(user, "Удалён источник истории обработки", treatment=entry.pk, reason="Расход сохранён при удалении животного", animal=entry.snapshot)
        return
    undo_expense(entry, user, "Удалена исходная запись ветобработки")
    entry.state, entry.issue = "deleted", "Исходная запись обработки удалена; расход сторнирован."
    entry.revision += 1
    entry.save()
    audit(user, "Обработка удалена", treatment=entry.pk, animal=entry.snapshot)
