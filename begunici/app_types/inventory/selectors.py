from decimal import Decimal

from .bridges import discover
from .models import AnimalCase, StockMovement
from .stock import available_lots


def pending_animals(*, meat_only=False):
    cases = {case.source_tag_id: case for case in AnimalCase.objects.select_related("receipt")}
    result = []
    for info in discover("pending"):
        if meat_only and info["kind"] != "meat":
            continue
        case = cases.get(info["tag_id"])
        if case and case.receipt.state == "confirmed":
            continue
        info["case"] = case
        info["document"] = case.receipt if case else None
        result.append(info)
    return result


def archive_rows():
    active_ids = set(available_lots().values_list("animal_id", flat=True))
    sales = StockMovement.objects.filter(
        kind="sale", document__kind="invoice", document__state="confirmed", lot__animal__receipt__state="confirmed",
    ).select_related("document", "lot__animal__receipt", "lot__product").order_by(
        "-document__date", "-document__confirmed_at", "-document_id", "lot__animal__tag_number", "id",
    )
    grouped, invoice_lines, sold_ids = {}, {}, set()
    for movement in sales:
        case, invoice = movement.lot.animal, movement.document
        sold_ids.add(case.pk)
        if invoice.pk not in invoice_lines:
            invoice_lines[invoice.pk] = {str(line["lot_id"]): line for line in invoice.payload.get("lines", [])}
        line = invoice_lines[invoice.pk].get(str(movement.lot_id), {})
        product = movement.lot.product
        name = line.get("name") or product.name
        counted = line["unit"] != "кг" if line.get("unit") else product.counted
        row = grouped.setdefault((case.pk, invoice.pk), {
            "case": case, "tag_number": case.tag_number, "snapshot": case.snapshot,
            "status": "Частично реализовано" if case.pk in active_ids else "Реализовано полностью",
            "archive_date": case.archive_date, "document": case.receipt, "invoice": invoice,
            "is_partial": case.pk in active_ids, "legacy": False, "sale_items": {},
        })
        item = row["sale_items"].setdefault((product.pk, name, counted), {
            "name": name, "weight": Decimal(0), "quantity": 0, "counted": counted,
        })
        item["weight"] -= movement.weight
        item["quantity"] -= movement.quantity
    result = list(grouped.values())
    for row in result:
        row["sale_items"] = list(row["sale_items"].values())
    # Keep closed, rejected-only cases without labelling them as sales.
    for case in AnimalCase.objects.filter(receipt__state="confirmed").select_related("receipt").order_by("-archive_date", "-id"):
        if case.pk not in active_ids and case.pk not in sold_ids:
            result.append({"case": case, "tag_number": case.tag_number, "snapshot": case.snapshot,
                           "status": "Учёт завершён без реализации", "archive_date": case.archive_date,
                           "document": case.receipt, "invoice": None, "sale_items": [], "is_partial": False, "legacy": False})
    for info in discover("legacy"):
        info["legacy"] = True
        result.append(info)
    return result


def stock_summary(lots):
    totals = {}
    for lot in lots:
        total = totals.setdefault(lot.product.code, {"name": lot.product.name, "weight": Decimal(0), "quantity": 0})
        total["weight"] += lot.available_weight
        total["quantity"] += lot.available_quantity
    return list(totals.values())
