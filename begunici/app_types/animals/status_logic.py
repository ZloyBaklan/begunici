from datetime import date

from django.db.models import Q

from begunici.app_types.veterinary.vet_models import Status

from .models import (
    ARCHIVE_STATUS_NAMES,
    Ewe,
    Lambing,
    LambingGroup,
    Maker,
    Ram,
    Sheep,
    STATUS_IN_GROUP,
    STATUS_INSEMINATED,
    STATUS_LAMBED,
    STATUS_NOT_INSEMINATED,
    STATUS_REPAIR,
    STATUS_UNDEFINED,
)


def get_status_by_name(status_name):
    return Status.objects.filter(status_type__iexact=status_name).first()


def get_required_status(status_name):
    status_obj = get_status_by_name(status_name)
    if not status_obj:
        raise ValueError(f"Статус «{status_name}» не найден в базе данных")
    return status_obj


def set_animal_status(animal, status_obj):
    if not animal or not status_obj or animal.animal_status_id == status_obj.id:
        return False

    animal.animal_status = status_obj
    animal.save()
    return True


def get_group_statuses():
    required = {
        "mother_in_group": STATUS_INSEMINATED,
        "father_in_group": STATUS_IN_GROUP,
        "mother_after_removal": STATUS_INSEMINATED,
        "father_after_removal": STATUS_REPAIR,
    }
    found = {key: get_status_by_name(name) for key, name in required.items()}
    missing = [name for key, name in required.items() if not found[key]]
    return found, missing


def get_default_child_status():
    return get_status_by_name(STATUS_UNDEFINED)


def get_lambing_children(lambing):
    mother_tag = (lambing.get_mother_tag() or "").strip()
    actual_date = lambing.actual_lambing_date
    if not mother_tag or not actual_date:
        return []

    children = []
    for model in (Ram, Ewe, Sheep, Maker):
        children.extend(
            model.objects.filter(
                mother__iexact=mother_tag,
                birth_date=actual_date,
            ).select_related("tag", "animal_status")
        )
    return children


def mother_has_active_reproduction(mother):
    if not mother:
        return False

    if isinstance(mother, Sheep):
        return (
            Lambing.objects.filter(sheep=mother, is_active=True).exists()
            or LambingGroup.objects.filter(sheep=mother, is_active=True).exists()
        )

    if isinstance(mother, Ewe):
        return (
            Lambing.objects.filter(ewe=mother, is_active=True).exists()
            or LambingGroup.objects.filter(ewes=mother, is_active=True).exists()
        )

    return False


def find_mothers_by_child(child_animal):
    mother_tag = (getattr(child_animal, "mother", "") or "").strip()
    if not mother_tag:
        return []

    mothers = []
    for model in (Sheep, Ewe):
        mother = (
            model.objects.filter(tag__tag_number__iexact=mother_tag)
            .select_related("tag", "animal_status")
            .first()
        )
        if mother:
            mothers.append(mother)
    return mothers


def set_mother_not_inseminated_if_ready(mother):
    if (
        not mother
        or not mother.animal_status
        or mother.animal_status.status_type != STATUS_LAMBED
    ):
        return False

    if mother_has_active_reproduction(mother):
        return False

    mother_tag = mother.tag.tag_number if getattr(mother, "tag", None) else ""
    relation_filter = Q()
    if isinstance(mother, Sheep):
        relation_filter |= Q(sheep=mother)
    elif isinstance(mother, Ewe):
        relation_filter |= Q(ewe=mother)
    if mother_tag:
        relation_filter |= Q(mother_tag_text__iexact=mother_tag)
    if not relation_filter:
        return False

    latest_lambing = (
        Lambing.objects.filter(
            is_active=False,
            actual_lambing_date__isnull=False,
        )
        .filter(relation_filter)
        .order_by("-actual_lambing_date", "-id")
        .first()
    )
    if not latest_lambing or (latest_lambing.number_of_lambs or 0) <= 0:
        return False

    children = get_lambing_children(latest_lambing)
    if len(children) < (latest_lambing.number_of_lambs or 0):
        return False

    if not all(child.date_otbivka or child.is_archived for child in children):
        return False

    return set_animal_status(mother, get_status_by_name(STATUS_NOT_INSEMINATED))


def set_mothers_not_inseminated_after_child_update(child_animal):
    updated = False
    for mother in find_mothers_by_child(child_animal):
        updated = set_mother_not_inseminated_if_ready(mother) or updated
    return updated


def is_archive_status(status):
    return bool(status and status.status_type in ARCHIVE_STATUS_NAMES)


def is_young_child_without_weaning(animal, as_of_date=None):
    as_of_date = as_of_date or date.today()
    if not animal or not animal.birth_date or animal.date_otbivka:
        return False
    return 0 <= (as_of_date - animal.birth_date).days < 100
