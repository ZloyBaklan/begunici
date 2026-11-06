from django import template
from decimal import Decimal, InvalidOperation
from begunici.app_types.inventory.permissions import can_manage_inventory
from ..plan import build_plan

register = template.Library()


@register.inclusion_tag("feed_inventory/barns/comparison.html", takes_context=True)
def feed_actual_plan(context, local_norms=False):
    from .. import barns
    for i in range(1, 5): barns.ensure_period(i)
    request = context.get("request")
    from django.core.exceptions import ValidationError
    try:
        data = barns.comparison(request.GET.get("feed_month") if request else None)
    except ValidationError:
        data = barns.comparison()
    return {"comparison": data, "inline": True, "local_norms": local_norms,
            "expanded": bool(request and request.GET.get("feed_month")),
            "can_edit": bool(request and can_manage_inventory(request.user))}


@register.inclusion_tag("feed_inventory/barns/map_bridge.html", takes_context=True)
def barn_feed_map_bridge(context):
    from ..barns import can_supply
    return {"allowed": can_supply(context["request"].user)}


@register.inclusion_tag("feed_inventory/barns/map_actions.html", takes_context=True)
def barn_feed_actions(context):
    from ..barns import can_supply
    return {"allowed": can_supply(context["request"].user)}


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
    request = context.get("request")
    if request is None:
        return {}
    return {"plan": build_plan(), "can_edit": can_manage_inventory(request.user),
            "editing": request.GET.get("edit_feed") == "1" and can_manage_inventory(request.user),
            "request": request,
            "csrf_token": context.get("csrf_token"), "messages": context.get("messages")}
