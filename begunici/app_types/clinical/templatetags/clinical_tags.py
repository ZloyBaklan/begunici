from django import template
from ..models import Episode
from ..permissions import can_view, can_manage, can_admit

register = template.Library()


@register.inclusion_tag("clinical/navigation.html", takes_context=True)
def clinical_navigation(context, active="planned"):
    from begunici.app_types.vet_inventory.permissions import can_view as stock_view
    user = context["request"].user
    return {"active": active, "clinical_visible": can_view(user), "stock_visible": stock_view(user)}


@register.inclusion_tag("clinical/animal_history.html", takes_context=True)
def clinical_history(context, animal):
    user = context["request"].user
    tag_id = animal.get("tag", {}).get("id") if isinstance(animal, dict) else animal.tag_id
    episodes = Episode.objects.filter(tag_id=tag_id).select_related("tag", "expense_document") if can_view(user) and tag_id else Episode.objects.none()
    return {"episodes": episodes, "clinical_visible": can_view(user)}


@register.inclusion_tag("clinical/assignment.html", takes_context=True)
def clinical_assignment(context, animal):
    user = context["request"].user
    episode = Episode.objects.filter(tag_id=animal.tag_id, closed_on__isnull=True).first() if animal.is_in_treatment and can_view(user) else None
    return {"animal": animal, "episode": episode, "clinical_visible": can_view(user), "clinical_can_admit": can_admit(user)}
