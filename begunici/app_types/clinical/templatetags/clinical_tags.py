from django import template
from django.contrib.auth.models import AnonymousUser
from datetime import date
from ..models import Episode
from ..permissions import can_view, can_manage, can_admit

register = template.Library()


@register.filter
def clinical_date(value):
    try:
        return (value if isinstance(value, date) else date.fromisoformat(str(value))).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return value or "Не указано"


@register.inclusion_tag("clinical/navigation.html", takes_context=True)
def clinical_navigation(context, active="planned"):
    from begunici.app_types.vet_inventory.permissions import can_view as stock_view
    user = getattr(context.get("request"), "user", AnonymousUser())
    return {"active": active, "clinical_visible": can_view(user), "stock_visible": stock_view(user)}


@register.inclusion_tag("clinical/animal_history.html", takes_context=True)
def clinical_history(context, animal):
    user = getattr(context.get("request"), "user", AnonymousUser())
    tag_id = animal.get("tag", {}).get("id") if isinstance(animal, dict) else animal.tag_id
    episodes = Episode.objects.filter(tag_id=tag_id).select_related("tag", "expense_document") if can_view(user) and tag_id else Episode.objects.none()
    return {"episodes": episodes, "clinical_visible": can_view(user)}


@register.inclusion_tag("clinical/assignment.html", takes_context=True)
def clinical_assignment(context, animal):
    user = getattr(context.get("request"), "user", AnonymousUser())
    episode = Episode.objects.filter(tag_id=animal.tag_id, closed_on__isnull=True).first() if animal.is_in_treatment and can_view(user) else None
    return {"animal": animal, "episode": episode, "clinical_visible": can_view(user), "clinical_can_admit": can_admit(user)}
