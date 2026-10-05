from decimal import Decimal

from .bridges import discover
from .models import AnimalCase
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
    result = []
    for case in AnimalCase.objects.filter(receipt__state="confirmed").select_related("receipt"):
        if case.pk not in active_ids:
            result.append({"case": case, "tag_number": case.tag_number, "snapshot": case.snapshot,
                           "status": "Учёт завершён, остатков нет", "archive_date": case.archive_date,
                           "document": case.receipt, "legacy": False})
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
