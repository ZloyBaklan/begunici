"""VET BRIDGE: all existing treatment entry points keep their original logic."""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from begunici.app_types.veterinary.vet_models import Veterinary
from .middleware import current_actor
from .treatments import capture, deleted


@receiver(post_save, sender=Veterinary, dispatch_uid="vet_inventory_capture")
def treatment_saved(sender, instance, created, raw=False, **kwargs):
    if not raw:
        capture(instance.pk, current_actor.get(), created=created)


@receiver(post_delete, sender=Veterinary, dispatch_uid="vet_inventory_delete")
def treatment_deleted(sender, instance, origin=None, **kwargs):
    origin_model = getattr(origin, "model", type(origin))
    deleted(instance.pk, current_actor.get(), cascade=origin_model is not Veterinary)
