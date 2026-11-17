from calendar import monthrange

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from begunici.app_types.veterinary.vet_models import Status
from begunici.app_types.vet_inventory.middleware import current_actor

from .models_user_log import UserActionLog
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
    STATUS_FATTENING,
    STATUS_NOT_INSEMINATED,
    STATUS_REPAIR,
    STATUS_UNDEFINED,
)

ANIMAL_TYPE_STATUS_RULES = {
    "Maker": {STATUS_FATTENING, STATUS_IN_GROUP, STATUS_REPAIR},
    "Ram": {STATUS_FATTENING, STATUS_REPAIR},
    "Ewe": {STATUS_UNDEFINED, STATUS_NOT_INSEMINATED, STATUS_INSEMINATED, STATUS_REPAIR},
    "Sheep": {STATUS_INSEMINATED, STATUS_LAMBED, STATUS_NOT_INSEMINATED},
}

ANIMAL_TYPE_ALIASES = {
    "maker": "Maker",
    "ram": "Ram",
    "ewe": "Ewe",
    "sheep": "Sheep",
}

ANIMAL_TYPE_LABELS = {
    "Maker": "баран-производитель",
    "Ram": "баранчик",
    "Ewe": "ярка",
    "Sheep": "овцематка",
}

LAMBED_STATUS_MISSING_CHILDREN_GRACE_MONTHS = 5


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


@transaction.atomic
def close_active_lambings_on_archive(animal, archive_date=None, *, actor=None):
    if not isinstance(animal, (Ewe, Sheep)) or not animal.is_archived:
        return []
    relation = "ewe_id" if isinstance(animal, Ewe) else "sheep_id"
    lambings = list(Lambing.objects.select_related("maker__tag", "ram__tag").select_for_update(of=("self",)).filter(
        **{relation: animal.pk}, is_active=True,
    ).order_by("pk"))
    if not lambings:
        return []
    if any(item.actual_lambing_date or (item.number_of_lambs or 0) > 0
           or item.dead_lambs_count > 0 for item in lambings):
        raise ValidationError(
            f"У {animal.tag.tag_number} в активном окоте уже указаны роды или ягнята. "
            "Сначала завершите этот окот, затем архивируйте мать."
        )

    archive_date = archive_date or timezone.localdate()
    archive_note = (
        f"Мать архивирована - {animal.animal_status.status_type}, {archive_date:%d.%m.%Y}"
    )
    for lambing in lambings:
        old_note = (lambing.note or "").rstrip(" \t\r\n")
        lambing.note = f"{old_note}\n{archive_note}" if old_note else archive_note
        lambing.is_active = False
        lambing.completion_type = Lambing.COMPLETION_UNSUCCESSFUL_INSEMINATION
        lambing.actual_lambing_date = None
        lambing.number_of_lambs = 0
        lambing.dead_lambs_count = 0
    # Do not run ordinary completion: it changes the parents' statuses and may convert an ewe.
    Lambing.objects.bulk_update(lambings, [
        "is_active", "completion_type", "actual_lambing_date", "number_of_lambs", "dead_lambs_count", "note",
    ])
    actor = actor if actor is not None else current_actor.get()
    if actor is not None and actor.is_authenticated:
        logs = []
        for lambing in lambings:
            father = lambing.get_father()
            father_tag = father.tag.tag_number if father and father.tag else "Неизвестно"
            parent_tags = [animal.tag.tag_number, father_tag]
            object_id = ", ".join(parent_tags)
            # Each tag can be 100 characters; preserve long pairs in metadata without truncation.
            if len(object_id) > UserActionLog._meta.get_field("object_id").max_length:
                object_id = str(lambing.pk)
            logs.append(UserActionLog(
                user=actor, action_type="Неудачное осеменение", object_type="Окот",
                object_id=object_id, description=lambing.note,
                additional_data={"source": "mother_archived", "lambing_id": lambing.pk, "parent_tags": parent_tags},
            ))
        UserActionLog.objects.bulk_create(logs)
    return [lambing.pk for lambing in lambings]


def normalize_animal_type(animal_type):
    if not animal_type:
        return None
    value = str(animal_type).strip()
    return ANIMAL_TYPE_ALIASES.get(value.lower(), value)


def get_allowed_active_status_names_for_animal_type(animal_type):
    normalized_type = normalize_animal_type(animal_type)
    allowed = ANIMAL_TYPE_STATUS_RULES.get(normalized_type)
    return set(allowed) if allowed is not None else None


def get_animal_status_validation_error(status_obj, animal_type, allow_archive=False):
    if not status_obj:
        return None

    status_name = status_obj.status_type
    normalized_type = normalize_animal_type(animal_type)

    if status_name == "Брак":
        return "Брак теперь отдельная отметка назначения, а не статус животного."

    if status_name in ARCHIVE_STATUS_NAMES:
        if allow_archive:
            return None
        return "Архивный статус можно установить только через отдельное действие архивирования."

    allowed_names = get_allowed_active_status_names_for_animal_type(normalized_type)
    if allowed_names is None:
        return None

    if status_name not in allowed_names:
        animal_label = ANIMAL_TYPE_LABELS.get(normalized_type, normalized_type or "животное")
        allowed_text = ", ".join(sorted(allowed_names))
        return (
            f"Статус «{status_name}» нельзя назначить для типа животного "
            f"«{animal_label}». Допустимые статусы: {allowed_text}."
        )

    return None


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


def get_active_group_for_animal(animal):
    if not animal:
        return None

    queryset = (
        LambingGroup.objects.filter(is_active=True)
        .select_related("maker__tag", "maker__place", "ram__tag", "ram__place")
    )

    if isinstance(animal, Maker):
        return queryset.filter(maker=animal).first()
    if isinstance(animal, Ram):
        return queryset.filter(ram=animal).first()
    if isinstance(animal, Sheep):
        return queryset.filter(sheep=animal).first()
    if isinstance(animal, Ewe):
        return queryset.filter(ewes=animal).first()
    return None


def get_group_place(group):
    father = group.get_father() if group else None
    if father and father.place_id:
        return father.place
    return group.place if group else None


def build_group_place_warning(animal, target_place=None):
    group = get_active_group_for_animal(animal)
    if not group:
        return None

    group_place = get_group_place(group)
    if target_place and group_place and target_place.id == group_place.id:
        return None

    tag_number = animal.tag.tag_number if getattr(animal, "tag", None) else "-"
    father_tag = group.get_father_tag() or "-"
    group_place_text = group_place.sheepfold if group_place else "место группы не указано"
    return (
        f"{tag_number} находится в группе с бараном-производителем/баранчиком "
        f"{father_tag} в месте «{group_place_text}». Перемещение нежелательно"
    )


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


def add_calendar_months(source_date, months):
    month_index = source_date.month - 1 + months
    target_year = source_date.year + month_index // 12
    target_month = month_index % 12 + 1
    target_day = min(source_date.day, monthrange(target_year, target_month)[1])
    return source_date.replace(year=target_year, month=target_month, day=target_day)


def is_lambing_old_enough_to_close_missing_children(lambing, as_of_date=None):
    if not lambing or not lambing.actual_lambing_date:
        return False

    as_of_date = as_of_date or timezone.localdate()
    close_date = add_calendar_months(
        lambing.actual_lambing_date,
        LAMBED_STATUS_MISSING_CHILDREN_GRACE_MONTHS,
    )
    return as_of_date >= close_date


def can_close_lambed_status_by_lambing_children(lambing, children, as_of_date=None):
    live_count = lambing.number_of_lambs or 0
    if live_count <= 0:
        return False

    if not all(child.date_otbivka or child.is_archived for child in children):
        return False

    if len(children) >= live_count:
        return True

    return is_lambing_old_enough_to_close_missing_children(lambing, as_of_date)


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
    if not can_close_lambed_status_by_lambing_children(latest_lambing, children):
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
    as_of_date = as_of_date or timezone.localdate()
    if not animal or not animal.birth_date or animal.date_otbivka:
        return False
    return 0 <= (as_of_date - animal.birth_date).days < 100
