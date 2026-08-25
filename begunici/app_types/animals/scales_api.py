import re
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import BasicAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from begunici.app_types.animals.models import Ewe, Maker, Ram, Sheep
from begunici.app_types.animals.models_user_log import UserActionLog
from begunici.app_types.veterinary.vet_models import (
    Place,
    PlaceMovement,
    WeightRecord,
)
from begunici.app_types.veterinary.vet_views import place_natural_sort_key


RSHN_PATTERN = re.compile(r"^RU[12][a-z0-9]{7}\d$", re.IGNORECASE)
ANIMAL_TYPES = (
    ("maker", "Баран-Производитель", Maker, "animals:maker-detail"),
    ("ram", "Баранчик", Ram, "animals:ram-detail"),
    ("ewe", "Ярка", Ewe, "animals:ewe-detail"),
    ("sheep", "Овцематка", Sheep, "animals:sheep-detail"),
)


class ScalesServicePermission(BasePermission):
    message = "Доступ разрешён только сервисному пользователю scales"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.username == "scales"
        )


def _log_scales_action(
    request,
    *,
    action_type,
    object_type,
    object_id,
    description,
):
    """Создаёт содержательный лог без технических деталей HTTP-запроса."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return

    UserActionLog.objects.create(
        user=user,
        action_type=action_type,
        object_type=object_type,
        object_id=object_id,
        description=description,
    )


def _short_tag_list(tag_numbers, limit=8):
    visible = list(tag_numbers[:limit])
    value = ", ".join(visible)
    if len(tag_numbers) > limit:
        value = f"{value}, ... (+{len(tag_numbers) - limit})"
    return value[:100]


def _error(message, code, http_status):
    return Response({"error": message, "code": code}, status=http_status)


def _normalize_rshn(value):
    normalized = str(value or "").strip()
    if not RSHN_PATTERN.fullmatch(normalized):
        raise ValueError("РСХН должен соответствовать формату RU1xxxxxxx0 или RU2xxxxxxx0")
    return f"RU{normalized[2:].lower()}"


def _place_payload(place):
    numbers = [int(value) for value in re.findall(r"\d+", place.sheepfold or "")]
    return {
        "id": place.id,
        "sheepfold": place.sheepfold,
        "barn_number": numbers[0] if len(numbers) >= 1 else None,
        "section_number": numbers[1] if len(numbers) >= 2 else None,
    }


def _normalize_optional_place_id(value):
    if value in (None, ""):
        return None
    try:
        place_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Не выбраны овчарня и отсек") from exc
    if place_id <= 0:
        raise ValueError("Не выбраны овчарня и отсек")
    return place_id


def _animal_basic_info(type_key, type_label, animal):
    dorper = None
    if animal.dorper_percentage is not None:
        percentage = float(animal.dorper_percentage)
        dorper = f"{percentage:g}%"
        if animal.is_manual_dorper:
            dorper += "*"

    father_data = animal.get_father_display()
    mother_data = animal.get_mother_display()
    last_weight = (
        WeightRecord.objects.filter(tag=animal.tag)
        .order_by("-weight_date", "-id")
        .first()
    )

    return {
        "tag_number": animal.tag.tag_number,
        "animal_type": type_label,
        "status": animal.animal_status.status_type if animal.animal_status else None,
        "age": animal.get_age_display(),
        "working_condition": (
            getattr(animal, "working_condition", None) if type_key == "maker" else None
        ),
        "place": animal.place.sheepfold if animal.place else None,
        "dorper": dorper,
        "purpose": "Брак" if animal.is_reject else None,
        "mother": mother_data.get("tag_number") if mother_data else None,
        "father": (
            father_data.get("display_name") or father_data.get("tag_number")
            if father_data
            else None
        ),
        "rshn_tag": animal.rshn_tag,
        "name": getattr(animal, "name", None) if type_key == "maker" else None,
        "date_otbivka": animal.date_otbivka.isoformat() if animal.date_otbivka else None,
        "last_weight": (
            {
                "weight": str(last_weight.weight),
                "date": last_weight.weight_date.isoformat(),
            }
            if last_weight
            else None
        ),
        "note": animal.note,
    }


def _animal_payload(type_key, type_label, route_name, animal, *, include_basic_info=False):
    place = animal.place.sheepfold if animal.place else None
    display_name = animal.tag.tag_number
    if type_key == "maker" and getattr(animal, "name", None):
        display_name = f"{animal.name}({animal.tag.tag_number})"
    payload = {
        "tag_number": animal.tag.tag_number,
        "display_name": display_name,
        "animal_type": type_key,
        "animal_type_label": type_label,
        "status": (
            animal.animal_status.status_type
            if animal.animal_status
            else "Нет статуса"
        ),
        "rshn_tag": animal.rshn_tag,
        "place": place,
        "place_id": animal.place_id,
        "detail_url": reverse(
            route_name,
            kwargs={"tag_number": animal.tag.tag_number},
        ),
    }
    if include_basic_info:
        payload["basic_info"] = _animal_basic_info(type_key, type_label, animal)
    return payload


def _move_animal_to_place(model, animal, new_place):
    if new_place is None or animal.place_id == new_place.id:
        return False, animal.place

    old_place = animal.place
    model.objects.filter(pk=animal.pk).update(place=new_place)
    PlaceMovement.objects.create(
        tag=animal.tag,
        old_place=old_place,
        new_place=new_place,
    )
    animal.place = new_place
    return True, old_place


def _log_automatic_movement(request, type_label, animal, old_place, new_place, reason):
    _log_scales_action(
        request,
        action_type="Перемещение животного",
        object_type=type_label,
        object_id=animal.tag.tag_number,
        description=(
            f"Бирка {animal.tag.tag_number}: "
            f"{old_place.sheepfold if old_place else 'место не указано'} -> "
            f"{new_place.sheepfold}; {reason}"
        ),
    )


def _active_animals(search="", *, with_rshn=False, limit=100):
    search = str(search or "").strip()
    items = []

    for type_key, type_label, model, route_name in ANIMAL_TYPES:
        queryset = model.objects.filter(is_archived=False).select_related(
            "tag",
            "place",
            "animal_status",
        )
        if with_rshn:
            queryset = queryset.exclude(rshn_tag__isnull=True).exclude(rshn_tag="")
        if search:
            search_filter = Q(tag__tag_number__icontains=search) | Q(
                rshn_tag__icontains=search
            )
            if model is Maker:
                search_filter |= Q(name__icontains=search)
            queryset = queryset.filter(search_filter)

        for animal in queryset.order_by("tag__tag_number")[:limit]:
            items.append((type_key, type_label, route_name, animal))

    items.sort(key=lambda item: item[3].tag.tag_number.lower())
    return items[:limit]


def _find_active_by_tag(tag_number, *, lock=False):
    tag_number = str(tag_number or "").strip()
    if not tag_number:
        return None

    for type_key, type_label, model, route_name in ANIMAL_TYPES:
        queryset = model.objects.filter(
            is_archived=False,
            tag__tag_number__iexact=tag_number,
        ).select_related("tag", "place", "animal_status")
        if lock:
            queryset = queryset.select_for_update(of=("self",))
        animal = queryset.first()
        if animal is not None:
            return type_key, type_label, model, route_name, animal
    return None


def _find_active_by_rshn(rshn_tag, *, lock=False):
    matches = []
    for type_key, type_label, model, route_name in ANIMAL_TYPES:
        queryset = model.objects.filter(
            is_archived=False,
            rshn_tag__iexact=rshn_tag,
        ).select_related("tag", "place", "animal_status")
        if lock:
            queryset = queryset.select_for_update(of=("self",))
        for animal in queryset:
            matches.append((type_key, type_label, model, route_name, animal))
    return matches


def _find_archived_by_rshn(rshn_tag, *, lock=False):
    matches = []
    for type_key, type_label, model, route_name in ANIMAL_TYPES:
        queryset = model.objects.filter(
            is_archived=True,
            rshn_tag__iexact=rshn_tag,
        ).select_related("tag", "place", "animal_status")
        if lock:
            queryset = queryset.select_for_update(of=("self",))
        for animal in queryset:
            matches.append((type_key, type_label, model, route_name, animal))
    return matches


@api_view(["GET"])
@authentication_classes([BasicAuthentication])
@permission_classes([ScalesServicePermission])
def animals(request):
    results = [
        _animal_payload(
            type_key,
            type_label,
            route_name,
            animal,
            include_basic_info=True,
        )
        for type_key, type_label, route_name, animal in _active_animals(
            request.query_params.get("search", "")
        )
    ]
    return Response({"results": results})


@api_view(["GET", "POST"])
@authentication_classes([BasicAuthentication])
@permission_classes([ScalesServicePermission])
def bindings(request):
    if request.method == "GET":
        results = [
            _animal_payload(type_key, type_label, route_name, animal)
            for type_key, type_label, route_name, animal in _active_animals(
                request.query_params.get("search", ""),
                with_rshn=True,
            )
        ]
        return Response({"results": results})

    tag_number = str(request.data.get("tag_number", "")).strip()
    force = request.data.get("force") is True
    if not tag_number:
        return _error("Не выбрана бирка животного", "tag_required", status.HTTP_400_BAD_REQUEST)

    try:
        rshn_tag = _normalize_rshn(request.data.get("rshn_tag"))
    except ValueError as exc:
        return _error(str(exc), "invalid_rshn", status.HTTP_400_BAD_REQUEST)

    try:
        place_id = _normalize_optional_place_id(request.data.get("place_id"))
    except ValueError as exc:
        return _error(str(exc), "place_required", status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        new_place = None
        if place_id is not None:
            try:
                new_place = Place.objects.select_for_update().get(pk=place_id)
            except Place.DoesNotExist:
                return _error(
                    "Выбранные овчарня и отсек не найдены",
                    "place_not_found",
                    status.HTTP_404_NOT_FOUND,
                )

        selected = _find_active_by_tag(tag_number, lock=True)
        if selected is None:
            return _error(
                "Активное животное с такой биркой не найдено",
                "animal_not_found",
                status.HTTP_404_NOT_FOUND,
            )

        type_key, type_label, model, route_name, animal = selected
        previous_rshn = animal.rshn_tag
        same_rshn = _find_active_by_rshn(rshn_tag, lock=True)
        archived_owners = _find_archived_by_rshn(rshn_tag, lock=True)
        if archived_owners:
            return Response(
                {
                    "error": "РСХН указан у архивного животного и не может быть перепривязан",
                    "code": "archived_binding_conflict",
                    "tag_numbers": [
                        archived_animal.tag.tag_number
                        for _type, _label, _model, _route, archived_animal in archived_owners
                    ],
                },
                status=status.HTTP_409_CONFLICT,
            )

        other_owners = [
            match for match in same_rshn if match[4].pk != animal.pk or match[2] is not model
        ]
        selected_has_other_rshn = bool(
            animal.rshn_tag and animal.rshn_tag.lower() != rshn_tag.lower()
        )
        detached_tag_numbers = [match[4].tag.tag_number for match in other_owners]

        if (other_owners or selected_has_other_rshn) and not force:
            conflicts = []
            if selected_has_other_rshn:
                conflicts.append(
                    {
                        "kind": "animal_has_other_rshn",
                        "tag_number": animal.tag.tag_number,
                        "rshn_tag": animal.rshn_tag,
                    }
                )
            for owner_type, _owner_label, _owner_model, owner_route, owner in other_owners:
                conflicts.append(
                    {
                        "kind": "rshn_already_bound",
                        "tag_number": owner.tag.tag_number,
                        "animal_type": owner_type,
                        "rshn_tag": owner.rshn_tag,
                        "detail_url": reverse(
                            owner_route,
                            kwargs={"tag_number": owner.tag.tag_number},
                        ),
                    }
                )
            return Response(
                {
                    "error": "Для этой привязки требуется подтверждение замены",
                    "code": "binding_conflict",
                    "requires_confirmation": True,
                    "conflicts": conflicts,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if force:
            for _owner_type, _owner_label, owner_model, _owner_route, owner in other_owners:
                owner_model.objects.filter(pk=owner.pk).update(rshn_tag=None)

        was_unchanged = bool(
            animal.rshn_tag and animal.rshn_tag.lower() == rshn_tag.lower()
        )
        if not was_unchanged:
            model.objects.filter(pk=animal.pk).update(rshn_tag=rshn_tag)
            animal.rshn_tag = rshn_tag

        was_rebound = bool(force and (selected_has_other_rshn or other_owners))
        if not was_unchanged or detached_tag_numbers:
            if was_rebound:
                details = [
                    f"РСХН {rshn_tag} перепривязан к бирке {animal.tag.tag_number}"
                ]
                if previous_rshn and previous_rshn.lower() != rshn_tag.lower():
                    details.append(f"Прежний РСХН бирки: {previous_rshn}")
                if detached_tag_numbers:
                    details.append(
                        f"Отвязан от бирок: {', '.join(detached_tag_numbers)}"
                    )
                action_type = "Перепривязка РСХН"
            else:
                details = [
                    f"Бирке {animal.tag.tag_number} присвоен РСХН {rshn_tag}"
                ]
                action_type = "Присвоение РСХН"

            _log_scales_action(
                request,
                action_type=action_type,
                object_type=type_label,
                object_id=animal.tag.tag_number,
                description="; ".join(details),
            )

        was_moved, old_place = _move_animal_to_place(model, animal, new_place)
        if was_moved:
            _log_automatic_movement(
                request,
                type_label,
                animal,
                old_place,
                new_place,
                "после привязки чипа",
            )

    payload = _animal_payload(type_key, type_label, route_name, animal)
    payload.update(
        {
            "created": not was_unchanged,
            "rebound": bool(force),
            "movement": (
                {
                    "moved": was_moved,
                    "skipped": not was_moved,
                    "place": _place_payload(new_place),
                }
                if new_place
                else None
            ),
        }
    )
    return Response(
        payload,
        status=status.HTTP_200_OK if was_unchanged else status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@authentication_classes([BasicAuthentication])
@permission_classes([ScalesServicePermission])
def identification(request):
    try:
        rshn_tag = _normalize_rshn(request.query_params.get("rshn"))
    except ValueError as exc:
        return _error(str(exc), "invalid_rshn", status.HTTP_400_BAD_REQUEST)

    matches = _find_active_by_rshn(rshn_tag)
    if not matches:
        return _error(
            "Бирка с таким чипом в базе не найдена",
            "animal_not_found",
            status.HTTP_404_NOT_FOUND,
        )
    if len(matches) > 1:
        return _error(
            "РСХН указан у нескольких активных животных",
            "duplicate_rshn",
            status.HTTP_409_CONFLICT,
        )

    type_key, type_label, _model, route_name, animal = matches[0]
    return Response(
        {
            "found": True,
            **_animal_payload(
                type_key,
                type_label,
                route_name,
                animal,
                include_basic_info=True,
            ),
        }
    )


@api_view(["GET"])
@authentication_classes([BasicAuthentication])
@permission_classes([ScalesServicePermission])
def places(request):
    sorted_places = sorted(Place.objects.all(), key=place_natural_sort_key)
    return Response(
        {
            "results": [
                _place_payload(place)
                for place in sorted_places
            ]
        }
    )


@api_view(["POST"])
@authentication_classes([BasicAuthentication])
@permission_classes([ScalesServicePermission])
def weights(request):
    tag_number = str(request.data.get("tag_number", "")).strip()
    try:
        weight = Decimal(str(request.data.get("weight", "")).replace(",", "."))
        if not weight.is_finite():
            raise InvalidOperation
        weight = weight.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return _error("Вес должен быть числом", "invalid_weight", status.HTTP_400_BAD_REQUEST)
    if weight <= 0 or weight >= Decimal("1000"):
        return _error(
            "Вес должен быть больше 0 и меньше 1000 кг",
            "invalid_weight",
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        place_id = _normalize_optional_place_id(request.data.get("place_id"))
    except ValueError as exc:
        return _error(str(exc), "place_required", status.HTTP_400_BAD_REQUEST)

    weight_date = timezone.localdate()
    with transaction.atomic():
        new_place = None
        if place_id is not None:
            try:
                new_place = Place.objects.select_for_update().get(pk=place_id)
            except Place.DoesNotExist:
                return _error(
                    "Выбранные овчарня и отсек не найдены",
                    "place_not_found",
                    status.HTTP_404_NOT_FOUND,
                )

        active_animal = _find_active_by_tag(tag_number, lock=True)
        if active_animal is None:
            return _error(
                "Активное животное с такой биркой не найдено",
                "animal_not_found",
                status.HTTP_404_NOT_FOUND,
            )
        _type_key, type_label, model, _route_name, animal = active_animal

        same_day_records = (
            WeightRecord.objects.select_for_update()
            .filter(tag=animal.tag, weight_date=weight_date)
            .order_by("-id")
        )
        record = same_day_records.first()
        was_updated = record is not None
        if record is None:
            old_weight = None
            record = WeightRecord.objects.create(
                tag=animal.tag,
                weight=weight,
                weight_date=weight_date,
            )
        else:
            old_weight = record.weight
            record.weight = weight
            record.save(update_fields=["weight"])
            same_day_records.exclude(pk=record.pk).delete()

        date_str = record.weight_date.strftime("%d.%m.%Y")
        if not was_updated:
            _log_scales_action(
                request,
                action_type="Добавление записи о весе",
                object_type="Запись о весе",
                object_id=animal.tag.tag_number,
                description=(
                    f"Добавлен вес {record.weight} кг; "
                    f"Дата: {date_str}; Бирка: {animal.tag.tag_number}"
                ),
            )
        elif old_weight != record.weight:
            _log_scales_action(
                request,
                action_type="Обновление записи о весе",
                object_type="Запись о весе",
                object_id=animal.tag.tag_number,
                description=(
                    f"Обновлен вес {old_weight} кг -> {record.weight} кг; "
                    f"Дата: {date_str}; Бирка: {animal.tag.tag_number}"
                ),
            )

        was_moved, old_place = _move_animal_to_place(model, animal, new_place)
        if was_moved:
            _log_automatic_movement(
                request,
                type_label,
                animal,
                old_place,
                new_place,
                "после взвешивания",
            )

    return Response(
        {
            "id": record.id,
            "tag_number": animal.tag.tag_number,
            "weight": str(record.weight),
            "weight_date": record.weight_date.isoformat(),
            "updated": was_updated,
            "movement": (
                {
                    "moved": was_moved,
                    "skipped": not was_moved,
                    "place": _place_payload(new_place),
                }
                if new_place
                else None
            ),
        },
        status=status.HTTP_200_OK if was_updated else status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@authentication_classes([BasicAuthentication])
@permission_classes([ScalesServicePermission])
def movements(request):
    raw_tag_numbers = request.data.get("tag_numbers")
    if not isinstance(raw_tag_numbers, list):
        return _error(
            "tag_numbers должен быть списком бирок",
            "invalid_tag_numbers",
            status.HTTP_400_BAD_REQUEST,
        )

    tag_numbers = []
    seen = set()
    for value in raw_tag_numbers:
        tag_number = str(value or "").strip()
        key = tag_number.lower()
        if tag_number and key not in seen:
            seen.add(key)
            tag_numbers.append(tag_number)
    if not tag_numbers:
        return _error(
            "Не выбраны животные для перемещения",
            "animals_required",
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        place_id = int(request.data.get("place_id"))
    except (TypeError, ValueError):
        return _error(
            "Не выбрана овчарня",
            "place_required",
            status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        try:
            new_place = Place.objects.select_for_update().get(pk=place_id)
        except Place.DoesNotExist:
            return _error(
                "Выбранная овчарня не найдена",
                "place_not_found",
                status.HTTP_404_NOT_FOUND,
            )

        resolved = []
        missing = []
        for tag_number in tag_numbers:
            match = _find_active_by_tag(tag_number, lock=True)
            if match is None:
                missing.append(tag_number)
            else:
                resolved.append(match)

        if missing:
            return Response(
                {
                    "error": "Часть животных больше недоступна для перемещения",
                    "code": "animals_changed",
                    "tag_numbers": missing,
                },
                status=status.HTTP_409_CONFLICT,
            )

        moved = []
        skipped = []
        for type_key, type_label, model, route_name, animal in resolved:
            if animal.place_id == new_place.id:
                skipped.append(animal.tag.tag_number)
                continue

            old_place = animal.place
            model.objects.filter(pk=animal.pk).update(place=new_place)
            PlaceMovement.objects.create(
                tag=animal.tag,
                old_place=old_place,
                new_place=new_place,
            )
            animal.place = new_place
            moved.append(_animal_payload(type_key, type_label, route_name, animal))

        moved_tag_numbers = [item["tag_number"] for item in moved]
        if moved_tag_numbers:
            _log_scales_action(
                request,
                action_type="Перемещение животных",
                object_type="Перемещение",
                object_id=_short_tag_list(moved_tag_numbers),
                description=(
                    f"Новое место: {new_place.sheepfold}; "
                    f"Перемещено животных: {len(moved_tag_numbers)}; "
                    f"Бирки: {', '.join(moved_tag_numbers)}"
                ),
            )

    return Response(
        {
            "moved": moved,
            "skipped": skipped,
            "place": _place_payload(new_place),
        }
    )
