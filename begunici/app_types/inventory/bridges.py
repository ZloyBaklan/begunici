"""All read-only integration with the existing animal/archive application.

No signals, monkey patches or writes to core tables. Discovery reads current
archive state, so bulk updates and the existing status workflow both work.
"""
import hashlib
import json
from datetime import date
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone

from begunici.app_types.animals.models import ArchiveAct, Ewe, Maker, Ram, Sheep
from begunici.app_types.veterinary.vet_models import StatusHistory, WeightRecord

ANIMAL_MODELS = {"maker": Maker, "ram": Ram, "ewe": Ewe, "sheep": Sheep}
SALE_STATUS = "Реализация в живом весе"
MEAT_STATUS = "Убой на мясо"


def start_date():
    return date.fromisoformat(getattr(settings, "INVENTORY_START_DATE", "2026-10-01"))


def plain(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False))


def fingerprint(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def animal_url(animal_type, tag_number):
    return reverse("animals:animals").removesuffix("main/") + f"{animal_type}/{quote(tag_number, safe='')}/info/"


def current_source_urls(tag_ids):
    """Resolve current cards by stable tag IDs without changing document snapshots."""
    urls = {}
    if not tag_ids:
        return urls
    for animal_type, model in ANIMAL_MODELS.items():
        animals = model.objects.filter(tag_id__in=tag_ids).select_related("tag").only("tag_id", "tag__tag_number")
        for animal in animals:
            urls[animal.tag_id] = animal_url(animal_type, animal.tag.tag_number)
    return urls


def source_queryset(model):
    return model.objects.select_related("tag", "animal_status", "place").prefetch_related(
        Prefetch("tag__archive_acts", queryset=ArchiveAct.objects.order_by("-updated_at", "-id"), to_attr="inventory_acts"),
        Prefetch("tag__status_history", queryset=StatusHistory.objects.order_by("-change_date", "-id"), to_attr="inventory_history"),
        Prefetch("tag__weightrecord_set", queryset=WeightRecord.objects.order_by("-weight_date", "-id"), to_attr="inventory_weights"),
    )


def source_animal(tag_id):
    for model in ANIMAL_MODELS.values():
        animal = source_queryset(model).filter(tag_id=tag_id).first()
        if animal:
            return animal
    raise ValidationError("Животное больше не найдено в основном сервисе.")


def source_info(animal):
    acts = getattr(animal.tag, "inventory_acts", None)
    if acts is None:
        acts = list(animal.tag.archive_acts.order_by("-updated_at", "-id"))
    status = str(animal.animal_status or "")
    act = next((a for a in acts if a.status_name == status), None)
    archive_date = act.status_date if act else None
    status_date = archive_date
    if not status_date:
        histories = getattr(animal.tag, "inventory_history", None)
        if histories is None:
            histories = animal.tag.status_history.order_by("-change_date", "-id")
        event = next((h for h in histories if h.new_status_id == animal.animal_status_id), None)
        if event:
            status_date = timezone.localtime(event.change_date).date() if timezone.is_aware(event.change_date) else event.change_date.date()
            if animal.is_archived:
                archive_date = status_date
    weights = getattr(animal.tag, "inventory_weights", None)
    if weights is None:
        weights = list(WeightRecord.objects.filter(tag=animal.tag).order_by("-weight_date", "-id"))
    latest_weight = weights[0] if weights else None
    animal_type = animal.get_animal_type().lower()
    snapshot = {field.name: getattr(animal, field.attname) for field in animal._meta.concrete_fields}
    snapshot.update({
        "tag_number": animal.tag.tag_number, "animal_type": animal_type,
        "status": status, "place": str(animal.place or ""),
        "sex": "male" if animal_type in {"maker", "ram"} else "female",
        "age_months": animal.get_age_months(archive_date),
        "age": animal.get_age_display(archive_date),
        "last_weight": latest_weight.weight if latest_weight else None,
        "weight_date": latest_weight.weight_date if latest_weight else None,
        "live_weight": act.live_weight if act and act.live_weight is not None else (latest_weight.weight if latest_weight else None),
        "fatness": act.get_fatness_display() if act else "",
        "vet_comment": act.diagnosis if act else "",
        "archive_date": archive_date,
        "status_date": status_date,
        "archive_act": {f.name: getattr(act, f.attname) for f in act._meta.concrete_fields} if act else None,
        "display_fields": [
            {"name": field.name, "label": str(field.verbose_name),
             "value": str(getattr(animal, field.name)) if field.is_relation else getattr(animal, field.name)}
            for field in animal._meta.concrete_fields if field.name != "id"
        ],
    })
    # Only archive business fields invalidate a pending/stock document. A rename
    # or unrelated note does not rewrite historical provenance or block a sale.
    signature = {
        "tag_id": animal.tag_id, "status": status, "archived": animal.is_archived,
        "date": archive_date,
        "act": {key: getattr(act, key) for key in (
            "id", "status_date", "act_date", "act_number", "live_weight", "fatness", "diagnosis", "act_group_key",
        )} if act else None,
    }
    return {
        "tag_id": animal.tag_id, "tag_number": animal.tag.tag_number,
        "animal_type": animal_type, "status": status, "archive_date": archive_date,
        "kind": "meat" if status == MEAT_STATUS else "live",
        "for_sale": animal.is_for_sale, "is_archived": animal.is_archived,
        "snapshot": plain(snapshot), "fingerprint": fingerprint(signature),
        "source_act_id": act.pk if act else None,
        "group_key": str(act.act_group_key) if act and act.act_group_key else "",
        # Core registers the same *-detail name for the HTML page and DRF's
        # resource. Reverse the unambiguous base instead of landing on JSON.
        "url": animal_url(animal_type, animal.tag.tag_number),
    }


def eligible(info):
    return info["is_archived"] and info["for_sale"] and info["status"] in {MEAT_STATUS, SALE_STATUS}


def require_eligible(info):
    if not eligible(info):
        raise ValidationError("Сначала животное должно получить назначение «К продаже», затем статус «Убой на мясо» либо «Реализация в живом весе».")
    if not info["archive_date"]:
        raise ValidationError("В основном архиве не указана дата выбытия. Уточните её до оформления склада.")
    if info["archive_date"] < start_date():
        raise ValidationError("Выбытие до 01.10.2026 относится к историческому архиву и не создаёт остатки.")


def discover(section):
    result = []
    for model in ANIMAL_MODELS.values():
        queryset = source_queryset(model)
        if section == "live":
            queryset = queryset.filter(is_archived=False, is_for_sale=True)
        else:
            queryset = queryset.filter(is_archived=True, animal_status__status_type__in=[SALE_STATUS, MEAT_STATUS])
        for animal in queryset:
            info = source_info(animal)
            if section == "live":
                result.append(info)
            elif section == "legacy":
                if info["archive_date"] and info["archive_date"] < start_date():
                    result.append(info)
            elif eligible(info) and (not info["archive_date"] or info["archive_date"] >= start_date()):
                result.append(info)
    return sorted(result, key=lambda row: row["tag_number"])


def validate_case_source(case):
    info = source_info(source_animal(case.source_tag_id))
    require_eligible(info)
    if info["fingerprint"] != case.source_fingerprint:
        raise ValidationError(f"{case.tag_number}: архивные данные изменились после создания складского акта. Требуется сверка с исходным архивом.")
    return info


def original_sp54(animal, user):
    from begunici.app_types.animals.archive_acts import generate_archive_act_workbook
    output = generate_archive_act_workbook(animal, user=user)
    if output is None:
        raise ValidationError("В основном сервисе не найден заполненный СП-54.")
    return output.getvalue()
