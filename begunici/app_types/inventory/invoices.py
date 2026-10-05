from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .documents import add_version, assert_editable, assert_revision
from .models import AuditEvent, Document, Order, StockLot, StockMovement
from .orders import fulfillment, refresh_state
from .permissions import require_inventory
from .stock import validate_withdrawal
from .validation import amount, count, rows


class IncompleteOrder(ValidationError):
    def __init__(self, report):
        self.report = report
        super().__init__("Заявка покрыта не полностью. " + "; ".join(report["missing"]) + ". Оставить её открытой для дополнительной накладной?")


def normalize_invoice(payload, order):
    if not isinstance(payload, dict):
        raise ValidationError("Некорректные данные накладной.")
    source_rows = rows(payload.get("lines"))
    lots = {lot.pk: lot for lot in StockLot.objects.select_related("product", "animal").filter(
        pk__in=[count(row.get("lot_id"), "Партия") for row in source_rows],
    )}
    order_lines = {line.pk: line for line in order.lines.all()} if order else {}
    clean, seen = [], set()
    for item in source_rows:
        lot_id = count(item.get("lot_id"), "Партия")
        lot = lots.get(lot_id)
        if not lot or lot_id in seen:
            raise ValidationError("Партия не найдена либо указана дважды. Объедините её в одну строку.")
        seen.add(lot_id)
        weight = amount(item.get("weight"))
        quantity = count(item.get("quantity", 0), allow_zero=not lot.product.counted)
        line_id = count(item["order_line_id"], "Строка заявки") if item.get("order_line_id") else None
        if order:
            if (lot.product.category == "live") != (order.kind == "live"):
                raise ValidationError("Тип продукции не соответствует заявке.")
            if line_id is None:
                matching = [line.pk for line in order_lines.values() if line.product_id == lot.product_id]
                if len(matching) == 1:
                    line_id = matching[0]
                else:
                    raise ValidationError("Выберите строку заявки для каждой позиции накладной.")
            if line_id not in order_lines or order_lines[line_id].product_id != lot.product_id:
                raise ValidationError("Строка заявки не принадлежит этой заявке или содержит другую номенклатуру.")
        elif line_id is not None:
            raise ValidationError("Сначала выберите заявку.")
        validate_withdrawal(lot, weight, quantity)
        clean.append({"lot_id": lot_id, "weight": str(weight), "quantity": quantity, "order_line_id": line_id})
    customer = str(payload.get("customer", "")).strip()[:200] or (order.customer if order else "")
    if not customer:
        raise ValidationError("Укажите получателя накладной.")
    return {"customer": customer, "lines": clean}


@transaction.atomic
def save_invoice(user, *, payload, order_id=None, document_id=None, expected_revision=None,
                 number="", upload=None, reason="", replace_confirmed=False):
    require_inventory(user)
    if document_id:
        document = Document.objects.select_for_update().get(pk=document_id)
        assert_editable(document)
        assert_revision(document, expected_revision)
        if document.kind != "invoice":
            raise ValidationError("Это не товарная накладная.")
    else:
        document = Document(kind="invoice", created_by=user)
    order = Order.objects.select_for_update().get(pk=order_id) if order_id else None
    if order and order.state == "closed":
        raise ValidationError("Заявка уже закрыта.")
    document.payload = normalize_invoice(payload, order)
    document.order, document.number, document.state = order, str(number).strip()[:100], "ready"
    document.save()
    add_version(document, user, upload=upload, reason=reason or "Составлена товарная накладная", replace_confirmed=replace_confirmed)
    return document


@transaction.atomic
def confirm_invoice(user, document_id, *, expected_revision, keep_open=False, close=True):
    require_inventory(user)
    document = Document.objects.select_for_update().get(pk=document_id)
    assert_revision(document, expected_revision)
    if document.kind != "invoice":
        raise ValidationError("Это не товарная накладная.")
    if document.state == "confirmed":
        return document
    if document.state != "ready":
        raise ValidationError("Накладная не готова к подтверждению.")
    order = Order.objects.select_for_update().get(pk=document.order_id) if document.order_id else None
    if order and order.state == "closed":
        raise ValidationError("Заявка уже закрыта другой накладной.")
    # PostgreSQL locks all lots in stable order. Drafts don't reserve stock;
    # availability is checked again inside the final transaction.
    locked = {lot.pk: lot for lot in StockLot.objects.select_for_update().filter(
        pk__in=[line["lot_id"] for line in document.payload["lines"]],
    ).order_by("pk")}
    payload = normalize_invoice(document.payload, order)
    entries = [(line["order_line_id"], locked[line["lot_id"]], amount(line["weight"]), line["quantity"]) for line in payload["lines"]]
    report = fulfillment(order, entries) if order else None
    if order and not report["complete"] and not keep_open:
        raise IncompleteOrder(report)
    for line_id, lot, weight, quantity in entries:
        StockMovement.objects.create(lot=lot, kind="sale", weight=-weight, quantity=-quantity,
                                     document=document, order_line_id=line_id, created_by=user)
    document.state, document.confirmed_by, document.confirmed_at = "confirmed", user, timezone.now()
    document.save(update_fields=["state", "confirmed_by", "confirmed_at"])
    if order:
        refresh_state(order, close=close and report["complete"])
    AuditEvent.objects.create(document=document, order=order, actor=user, action="invoice_confirmed", data={
        "revision": document.revision, "kept_open": bool(order and not report["complete"]), "report": report,
    })
    return document


@transaction.atomic
def reverse_invoice(user, document_id, *, reason, expected_revision):
    require_inventory(user)
    if not str(reason).strip():
        raise ValidationError("Укажите причину сторно.")
    document = Document.objects.select_for_update().get(pk=document_id)
    assert_revision(document, expected_revision)
    if document.kind != "invoice":
        raise ValidationError("Сторно доступно для товарной накладной.")
    if document.state == "reversed":
        return document
    if document.state != "confirmed":
        raise ValidationError("Сторнировать можно только подтверждённую накладную.")
    order = Order.objects.select_for_update().get(pk=document.order_id) if document.order_id else None
    movements = list(document.movements.filter(kind="sale"))
    list(StockLot.objects.select_for_update().filter(pk__in=[item.lot_id for item in movements]).order_by("pk"))
    for item in movements:
        StockMovement.objects.create(lot_id=item.lot_id, kind="reversal", weight=-item.weight, quantity=-item.quantity,
                                     document=document, order_line=item.order_line, reason=str(reason).strip(), created_by=user)
    document.state = "reversed"
    document.save(update_fields=["state"])
    if order:
        refresh_state(order)
    AuditEvent.objects.create(document=document, order=order, actor=user, action="invoice_reversed", data={"reason": str(reason).strip()})
    return document
