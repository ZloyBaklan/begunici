from django import template

from ..animal_types import type_label
from ..models import AnimalCase
from ..permissions import can_access_slaughter, can_manage_inventory

register = template.Library()
register.filter("animal_type_label", type_label)


@register.simple_tag(takes_context=True)
def inventory_access(context):
    return can_manage_inventory(context["request"].user)


@register.inclusion_tag("inventory/includes/archive_hint.html", takes_context=True)
def inventory_archive_hint(context):
    return {"allowed": can_access_slaughter(context["request"].user)}


@register.inclusion_tag("inventory/includes/home_button.html", takes_context=True)
def inventory_home_button(context):
    return {"allowed": can_manage_inventory(context["request"].user)}


@register.inclusion_tag("inventory/includes/acts_button.html", takes_context=True)
def inventory_acts_button(context):
    return {"allowed": can_access_slaughter(context["request"].user)}


@register.inclusion_tag("inventory/includes/animal_button.html", takes_context=True)
def inventory_animal_button(context, animal):
    if not can_manage_inventory(context["request"].user):
        return {}
    case = AnimalCase.objects.filter(source_tag_id=animal.tag_id).select_related("receipt").first()
    label = "Складской учёт"
    if case and case.receipt.state == "confirmed":
        label = "Акт подтверждён · товарные накладные"
    elif animal.is_archived and str(animal.animal_status) == "Реализация в живом весе" and animal.is_for_sale:
        label = "Подтвердить акт реализации"
    return {"allowed": animal.is_for_sale or bool(case), "tag_id": animal.tag_id, "label": label}


@register.filter
def item(mapping, key):
    return mapping.get(str(key), {}) if isinstance(mapping, dict) else None
