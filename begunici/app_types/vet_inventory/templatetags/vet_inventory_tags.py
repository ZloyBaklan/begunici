from decimal import Decimal, InvalidOperation
from django import template
from begunici.app_types.inventory.templatetags.inventory_tags import context_user
from ..permissions import can_view
from ..services import number

register = template.Library()


@register.filter
def vet_quantity(value):
    try:
        decimal = Decimal(str(value))
        return number(decimal).replace(".", ",") if decimal.is_finite() else "—"
    except (InvalidOperation, TypeError, ValueError):
        return "—"


@register.inclusion_tag("vet_inventory/entry.html", takes_context=True)
def vet_stock_entry(context, animal=None):
    return {"allowed": can_view(context_user(context)), "tag_id": getattr(animal, "tag_id", None)}


@register.inclusion_tag("vet_inventory/dashboard_card.html", takes_context=True)
def vet_stock_card(context):
    return {"allowed": can_view(context_user(context))}
