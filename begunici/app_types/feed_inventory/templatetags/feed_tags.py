from django import template
from decimal import Decimal, InvalidOperation
from begunici.app_types.inventory.permissions import can_manage_inventory
from ..plan import build_plan

register = template.Library()


@register.inclusion_tag("feed_inventory/barns/comparison.html", takes_context=True)
def feed_actual_plan(context, local_norms=False):
    from .. import barns
    request = context.get("request")
    if request is None:
        return {}
    if request and barns.can_supply(request.user):
        for i in range(1, 5):
            barns.ensure_period(i)
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
    from ..barns import can_supply, can_view_barns
    from ..models import FeedProduct
    import uuid
    from datetime import timedelta
    from django.utils import timezone
    request = context.get("request")
    if request is None:
        return {"allowed": False}
    user = request.user
    allowed = can_view_barns(user)
    return {"allowed": allowed, "can_supply": can_supply(user), "can_writeoff": can_manage_inventory(user),
            "products": FeedProduct.objects.all() if allowed else [], "barn_numbers": range(1, 5),
            "token": uuid.uuid4(), "csrf_token": context.get("csrf_token"),
            "previous_month": (timezone.localdate().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")}


@register.inclusion_tag("feed_inventory/barns/map_actions.html", takes_context=True)
def barn_feed_actions(context):
    from ..barns import can_supply, can_view_barns
    request = context.get("request")
    if request is None:
        return {"allowed": False}
    user = request.user
    return {"allowed": can_view_barns(user), "can_supply": can_supply(user)}


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
