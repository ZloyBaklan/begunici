from django import template
from decimal import Decimal, InvalidOperation
from begunici.app_types.inventory.permissions import can_manage_inventory
from ..plan import build_plan

register = template.Library()


@register.filter
def feed_quantity(value):
    if value is None or value == "":
        return "—"
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            return "—"
        result = format(result.quantize(Decimal("0.001")), "f").rstrip("0").rstrip(".")
        return result.replace(".", ",")
    except (InvalidOperation, ValueError):
        return str(value)


@register.inclusion_tag("feed_inventory/plan_card.html", takes_context=True)
def feed_plan_card(context):
    request = context["request"]
    return {"plan": build_plan(), "can_edit": can_manage_inventory(request.user),
            "csrf_token": context.get("csrf_token"), "messages": context.get("messages")}
