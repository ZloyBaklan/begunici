from decimal import Decimal, InvalidOperation
from datetime import date
from django import template
from begunici.app_types.inventory.templatetags.inventory_tags import context_user
from ..permissions import can_view
from ..services import number

register = template.Library()


@register.filter
def vet_date(value):
    if not value:
        return "—"
    try:
        return date.fromisoformat(str(value)).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return value


@register.simple_tag(takes_context=True)
def vet_inventory_access(context):
    return can_view(context_user(context))


@register.filter
def vet_quantity(value):
    try:
        decimal = Decimal(str(value))
        return number(decimal).replace(".", ",") if decimal.is_finite() else "—"
    except (InvalidOperation, TypeError, ValueError):
        return "—"


@register.filter
def vet_calculation_mode(calculation):
    if not isinstance(calculation, dict):
        return "Норма не задана"
    label = str(calculation.get("mode_label") or "")
    if (calculation.get("mode") == "step" or label.startswith("На каждые")) and (
            not label or label.startswith("На каждые")):
        try:
            step = Decimal(str(calculation.get("weight_step")))
        except (InvalidOperation, TypeError, ValueError):
            pass
        else:
            if step.is_finite() and step > 0:
                return f"На каждые {number(step).replace('.', ',')} кг"
    return label or "Норма не задана"


@register.filter
def vet_calculation_basis(calculation):
    label = vet_calculation_mode(calculation)
    if not isinstance(calculation, dict) or label == "Уточнено вручную" or calculation.get("mode") not in {"head", "weight", "step", "bands"}:
        return label
    condition = calculation.get("matched_condition")
    rate = condition.get("rate") if isinstance(condition, dict) else calculation.get("rate")
    unit = calculation.get("dose_unit_label") or calculation.get("unit")
    try:
        rate = Decimal(str(rate))
    except (InvalidOperation, TypeError, ValueError):
        return label
    if not rate.is_finite() or rate < 0 or not unit:
        return label
    if calculation.get("dose_basis") == "active":
        unit += " действующего вещества"
    return f"{label} {number(rate).replace('.', ',')} {unit}"


@register.filter
def vet_calculation_concentration(calculation):
    if not isinstance(calculation, dict):
        return ""
    value = vet_quantity(calculation.get("concentration"))
    if value == "—":
        return ""
    from ..models import VetProduct
    kind = calculation.get("concentration_unit")
    label = dict(VetProduct._meta.get_field("concentration_unit").choices).get(kind)
    if not label:
        return f"{value} (единица не указана)"
    return value + ("" if kind.startswith("percent_") else " ") + label


@register.filter
def vet_treatment_name(entry):
    selections = entry.calculation.get("group_expenses")
    return selections[0]["name"] if selections else entry.product.name if entry.product else "Не связан"


@register.filter
def vet_treatment_quantity(entry):
    selections = entry.calculation.get("group_expenses")
    return selections[0]["amount"] if selections else entry.quantity


@register.filter
def vet_treatment_unit(entry):
    selections = entry.calculation.get("group_expenses")
    if selections:
        return selections[0]["unit_label"] + (" действующего вещества" if selections[0]["basis"] == "active" else "")
    return entry.product.get_unit_display() if entry.product else ""


@register.inclusion_tag("vet_inventory/entry.html", takes_context=True)
def vet_stock_entry(context, animal=None):
    return {"allowed": can_view(context_user(context)), "tag_id": getattr(animal, "tag_id", None)}


@register.inclusion_tag("vet_inventory/dashboard_card.html", takes_context=True)
def vet_stock_card(context):
    return {"allowed": can_view(context_user(context))}
