"""Read-only display of current data and immutable, possibly older snapshots."""
from datetime import date
from decimal import Decimal

from .animal_types import type_label


def display_date(value):
    if not value:
        return "—"
    return date.fromisoformat(str(value)[:10]).strftime("%d.%m.%Y")


def carcass_weight(snapshot, case=None):
    value = snapshot.get("carcass_weight")
    if value is not None and value != "":
        return value, ""
    if case and case.receipt.kind == "sp55" and case.receipt.state == "confirmed":
        # Use the original confirmed receipt, never the changing stock balance.
        outputs = [row for row in case.receipt.payload.get("outputs", [])
                   if str(row.get("animal_id")) == str(case.pk) and row.get("product") in {"carcass", "half"}]
        carcasses = [row for row in outputs if row["product"] == "carcass"]
        halves = [row for row in outputs if row["product"] == "half"]
        # A single half or a set of cuts does not establish the full carcass mass.
        if carcasses or sum(row["quantity"] for row in halves) == 2:
            weight = sum((Decimal(row["weight"]) for row in outputs), Decimal(0))
            return format(weight, "f"), f"По подтверждённому {case.receipt}"
    return None, ""


def animal_display(snapshot, case=None):
    weight, weight_source = carcass_weight(snapshot, case)
    status_date = display_date(snapshot.get("status_date") or snapshot.get("archive_date"))
    fields = [{"label": "Тип животного", "value": type_label(snapshot.get("animal_type"))},
              {"label": "Дата статуса", "value": status_date}]
    for original in snapshot.get("display_fields", []):
        field = dict(original)
        value = field.get("value")
        if field.get("name") == "carcass_weight" or field["label"] == "Вес туши (кг)":
            value = weight
            field["note"] = weight_source
        field["is_boolean"] = isinstance(value, bool)
        if not field["is_boolean"]:
            if field["label"].lower().startswith("дата") and value:
                value = display_date(value)
            if value is None or value == "":
                value = "—"
        field["value"] = value
        fields.append(field)
    return {"fields": fields, "status_date": status_date, "carcass_weight": weight,
            "carcass_weight_source": weight_source}
