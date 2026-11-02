"""CLINICAL BRIDGE: ordinary veterinary treatments retain their stock behaviour."""
from contextvars import ContextVar
from contextlib import contextmanager
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save, post_save
from begunici.app_types.animals.models import Maker, Ram, Ewe, Sheep, ARCHIVE_STATUS_NAMES
from begunici.app_types.vet_inventory.middleware import current_actor

internal_change = ContextVar("clinical_internal_change", default=False)


@contextmanager
def completing():
    token = internal_change.set(True)
    try:
        yield
    finally:
        internal_change.reset(token)


def transition_required(animal, data):
    from .models import Episode
    episode = Episode.objects.filter(tag_id=animal.tag_id, closed_on__isnull=True).first()
    selected = data.get("animal_status")
    if episode and (data.get("is_in_treatment") is False or (selected and selected.status_type in ARCHIVE_STATUS_NAMES)):
        return episode
    return None


def validate_transition(animal, data, user):
    from rest_framework.exceptions import ValidationError as APIValidationError
    from .permissions import require_admit
    if data.get("is_in_treatment", animal.is_in_treatment):
        selected = data.get("animal_status", animal.animal_status)
        if data.get("is_archived", animal.is_archived) or (selected and selected.status_type in ARCHIVE_STATUS_NAMES):
            raise APIValidationError({"is_in_treatment": "Архивное животное нельзя направить на лечение."})
    if "is_in_treatment" in data and data["is_in_treatment"] != animal.is_in_treatment:
        require_admit(user)
    if not internal_change.get():
        episode = transition_required(animal, data)
        if episode:
            raise APIValidationError({"treatment_required": "Сначала подтвердите исход лечения и расход препаратов.", "treatment_url": f"/animals/treatment/{episode.pk}/?finish=1"})


def protect(sender, instance, raw=False, **kwargs):
    if raw or internal_change.get() or not instance.tag_id:
        return
    from .models import Episode
    if instance.is_in_treatment and (instance.is_archived or (instance.animal_status and instance.animal_status.status_type in ARCHIVE_STATUS_NAMES)):
        raise ValidationError("Архивное животное нельзя направить на лечение.")
    if Episode.objects.filter(tag_id=instance.tag_id, closed_on__isnull=True).exists():
        if not instance.is_in_treatment or (instance.animal_status and instance.animal_status.status_type in ARCHIVE_STATUS_NAMES):
            raise ValidationError("Сначала завершите лечение в журнале и подтвердите расход препаратов.")


def capture(sender, instance, raw=False, **kwargs):
    if raw or internal_change.get() or not instance.is_in_treatment or instance.is_archived:
        return
    from .services import ensure_episode
    ensure_episode(instance, current_actor.get())


for model in (Maker, Ram, Ewe, Sheep):
    pre_save.connect(protect, sender=model, dispatch_uid=f"clinical_protect_{model.__name__}", weak=False)
    post_save.connect(capture, sender=model, dispatch_uid=f"clinical_capture_{model.__name__}", weak=False)
