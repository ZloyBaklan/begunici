import re
from decimal import Decimal, InvalidOperation, ROUND_CEILING

from dateutil.relativedelta import relativedelta


# Base norms and section limits from the supplied workbook's third sheet.
GROUPS = (
    ("producers", "Бараны-производители", "2", "0.5", 25),
    ("teasers", "Бараны-пробники", "1.8", "0.5", 50),
    ("barren_mothers", "Матки холостые", "0.7", "0.3", 250),
    ("pregnant_mothers", "Матки суягные", "1", "0.3", 250),
    ("lactating_0_10", "Матки подсосные с ягнятами до 10 дней", "1.2", "0.3", 120),
    ("lactating_winter", "Матки подсосные старше 10 дней, зимнее ягнение", "1.2", "0.3", 120),
    ("lactating_spring", "Матки подсосные старше 10 дней, весеннее ягнение", "1", "0.3", 120),
    ("repair_young", "Ремонтный молодняк", "0.7", "0.3", 250),
    ("lambs_0_45", "Ягнята до 45 дней", "0.3", "0.15", 25),
    ("lambs_45_4", "Ягнята старше 45 дней до 4 месяцев", "0.4", "0.2", 50),
    ("fattening_adults", "Откормочное поголовье взрослое", "0.5", "0.3", 250),
    ("fattening_young", "Откормочное поголовье молодняк", "0.4", "0.25", 250),
    ("wethers", "Валухи", "0.5", "0.3", 250),
)
GROUP_IDS = frozenset(group[0] for group in GROUPS)
FATTENING_GROUPS = {"fattening_young", "fattening_adults"}
PARAMETER_LABELS = {
    "area_limit": "Лимит площади здания, м²",
    "length": "Длина овчарни, м",
    "central_width": "Ширина кормового проезда, м",
    "include_wall_passages": "Техпроходы вдоль стен",
    "wall_passage_width": "Ширина одного техпрохода, м",
    "housing_width": "Ширина зоны содержания с каждой стороны, м",
    "breeding_premium_percent": "Племенная надбавка площади, %",
    "doors_left": "Количество дверей слева",
    "doors_right": "Количество дверей справа",
    "door_width": "Ширина одной двери, м",
    "feeding_mode": "Режим кормления откормочного поголовья",
}
DEFAULT_PARAMETERS = {
    "area_limit": "1500", "length": "140", "central_width": "2.6",
    "include_wall_passages": False, "wall_passage_width": "1",
    "housing_width": "4", "breeding_premium_percent": "20",
    "doors_left": 3, "doors_right": 5, "door_width": "1.2",
    "feeding_mode": "rationed",
}
PLACE_PATTERN = re.compile(r"^Овчарня\s+(\d+)\s+Отсек\s+(\d+)\s*$", re.IGNORECASE)


class CalculatorInputError(ValueError):
    pass


def _number(value, label, maximum=1000000, integer=False, positive=False):
    try:
        if isinstance(value, bool) or value is None or str(value).strip() == "":
            raise ValueError
        number = Decimal(str(value).strip().replace(",", "."))
        if not number.is_finite() or number < 0 or number > maximum:
            raise ValueError
        if positive and number == 0:
            raise ValueError
        if integer and number != number.to_integral_value():
            raise ValueError
        if not integer and number.as_tuple().exponent < -4:
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        requirement = "целое число" if integer else "число (до 4 знаков после запятой)"
        lower = "больше 0" if positive else "не меньше 0"
        raise CalculatorInputError(f"{label}: требуется {requirement}, {lower} и не больше {maximum}")
    return int(number) if integer else number


def normalize_parameters(raw):
    if not isinstance(raw, dict):
        raise CalculatorInputError("Параметры овчарни должны быть объектом")
    if set(raw) - set(DEFAULT_PARAMETERS):
        raise CalculatorInputError("Переданы неизвестные параметры овчарни")
    parameters = {**DEFAULT_PARAMETERS, **raw}
    for key in ("area_limit", "length", "central_width", "wall_passage_width", "housing_width", "door_width", "breeding_premium_percent"):
        parameters[key] = _number(
            parameters[key], PARAMETER_LABELS[key],
            maximum=20 if key == "breeding_premium_percent" else 1000000,
            positive=key in {"area_limit", "length", "housing_width"},
        )
    for key in ("doors_left", "doors_right"):
        parameters[key] = _number(parameters[key], PARAMETER_LABELS[key], maximum=10000, integer=True)
    if type(parameters["include_wall_passages"]) is not bool:
        raise CalculatorInputError("Техпроходы вдоль стен: требуется значение Да или Нет")
    if not isinstance(parameters["feeding_mode"], str) or parameters["feeding_mode"] not in {"rationed", "free_access"}:
        raise CalculatorInputError("Выберите допустимый режим кормления")
    if (parameters["doors_left"] or parameters["doors_right"]) and not parameters["door_width"]:
        raise CalculatorInputError("При наличии дверей их ширина должна быть больше 0")
    return parameters


def parameters_to_json(parameters):
    return {
        key: format(value.normalize(), "f") if isinstance(value, Decimal) else value
        for key, value in parameters.items()
    }


def empty_composition():
    return {key: {"left": 0, "right": 0} for key, *_ in GROUPS}


def normalize_composition(raw):
    if not isinstance(raw, dict):
        raise CalculatorInputError("Компоновка должна быть объектом")
    if set(raw) - GROUP_IDS:
        raise CalculatorInputError("В компоновке переданы неизвестные группы животных")
    result = empty_composition()
    for key, label, *_ in GROUPS:
        counts = raw.get(key, {})
        if not isinstance(counts, dict) or set(counts) - {"left", "right"}:
            raise CalculatorInputError(f"{label}: укажите поголовье слева и справа")
        for side, side_label in (("left", "слева"), ("right", "справа")):
            result[key][side] = _number(counts.get(side, 0), f"{label}, {side_label}", integer=True)
    return result


def normalize_barn_number(value, allow_arbitrary=False):
    if allow_arbitrary and value in (None, "", "arbitrary"):
        return None
    number = _number(value, "Номер овчарни", maximum=4, integer=True, positive=True)
    return number


def calculate_barn(raw_parameters, raw_composition):
    parameters = normalize_parameters(raw_parameters)
    composition = normalize_composition(raw_composition)
    premium = 1 + parameters["breeding_premium_percent"] / 100
    length = parameters["length"]
    zone = parameters["housing_width"]
    passage_width = parameters["wall_passage_width"] if parameters["include_wall_passages"] else Decimal(0)
    building_width = parameters["central_width"] + 2 * zone + 2 * passage_width
    sides = {
        side: {"heads": 0, "area_required": Decimal(0), "feeding_required": Decimal(0), "sections_required": 0}
        for side in ("left", "right")
    }
    rows = []
    for key, label, base_area, base_front, section_limit in GROUPS:
        area_norm = Decimal(base_area) * premium
        divisor = 2 if parameters["feeding_mode"] == "free_access" and key in FATTENING_GROUPS else 1
        front_norm = Decimal(base_front) / divisor
        row = {"key": key, "label": label, "area_norm": float(area_norm), "front_norm": float(front_norm), "section_limit": section_limit}
        for side in sides:
            heads = composition[key][side]
            area = heads * area_norm
            front = heads * front_norm
            sections = int((Decimal(heads) / section_limit).to_integral_value(rounding=ROUND_CEILING))
            sides[side]["heads"] += heads
            sides[side]["area_required"] += area
            sides[side]["feeding_required"] += front
            sides[side]["sections_required"] += sections
            row[side] = {"heads": heads, "area": float(area), "feeding": float(front), "sections": sections}
        rows.append(row)
    for side, values in sides.items():
        doors = parameters[f"doors_{side}"]
        deduction = doors * parameters["door_width"]
        available_front = max(Decimal(0), length - deduction)
        values.update({
            "area_available": length * zone,
            "area_remaining": length * zone - values["area_required"],
            "doors": doors, "door_deduction": deduction,
            "feeding_available": available_front,
            "feeding_remaining": available_front - values["feeding_required"],
        })
    building_area = length * building_width
    checks = [{"key": "building_area", "label": "Площадь здания", "unit": "м²", "available": parameters["area_limit"], "required": building_area}]
    for side, label in (("left", "слева"), ("right", "справа")):
        checks.extend([
            {"key": f"area_{side}", "label": f"Площадь содержания {label}", "unit": "м²", "available": sides[side]["area_available"], "required": sides[side]["area_required"]},
            {"key": f"feeding_{side}", "label": f"Кормовой фронт {label}", "unit": "м", "available": sides[side]["feeding_available"], "required": sides[side]["feeding_required"]},
        ])
    for check in checks:
        remaining = check["available"] - check["required"]
        check.update({"remaining": float(remaining), "passed": remaining >= 0})
        check["available"] = float(check["available"])
        check["required"] = float(check["required"])
    return {
        "rows": rows, "checks": checks, "passed": all(check["passed"] for check in checks),
        "total_heads": sum(side["heads"] for side in sides.values()),
        "building": {
            "width": float(building_width), "max_width": float(parameters["area_limit"] / length),
            "area": float(building_area), "area_remaining": float(parameters["area_limit"] - building_area),
            "central_passage_area": float(length * parameters["central_width"]),
            "wall_passages_area": float(2 * length * passage_width),
        },
        "sides": {
            side: {key: float(value) if isinstance(value, Decimal) else value for key, value in values.items()}
            for side, values in sides.items()
        },
    }


def classify_animal(animal_type, birth_date, status_name, lambing_date, as_of_date):
    if birth_date and birth_date > as_of_date:
        return None, "Дата рождения находится в будущем"
    if animal_type in {"sheep", "ewe"}:
        if status_name == "Осемененная":
            return "pregnant_mothers", None
        if status_name == "Объягненная":
            if not lambing_date or lambing_date > as_of_date:
                return None, "Для объягненной матери не найден завершённый окот с живыми ягнятами"
            if (as_of_date - lambing_date).days <= 10:
                return "lactating_0_10", None
            winter = lambing_date.month in {9, 10, 11, 12, 1, 2}
            return "lactating_winter" if winter else "lactating_spring", None
    if animal_type == "maker" and status_name != "Откорм":
        return "producers", None
    if animal_type == "ram" and status_name == "В группе":
        return "producers", None
    if animal_type == "sheep" and status_name in {"Неосемененная", "В группе"}:
        return "barren_mothers", None
    if not birth_date:
        return None, "Не указана дата рождения: невозможно определить возрастную группу"
    # Calendar anniversaries avoid rounded age values changing a group too early.
    if animal_type in {"ewe", "ram"}:
        if (as_of_date - birth_date).days <= 45:
            return "lambs_0_45", None
        if as_of_date < birth_date + relativedelta(months=4):
            return "lambs_45_4", None
    if status_name == "Ремонт":
        return "repair_young", None
    if animal_type == "ewe" and status_name in {"Неосемененная", "В группе"}:
        return "barren_mothers", None
    if (status_name in {"Откорм", "Не определено", None, ""} and animal_type in {"ewe", "ram", "maker"}) or status_name == "Откорм":
        adult = as_of_date >= birth_date + relativedelta(months=10)
        return "fattening_adults" if adult else "fattening_young", None
    return None, f"Не определена нормативная группа для статуса «{status_name or 'Не указан'}»"


def build_factual_composition(barn_number, as_of_date=None):
    from django.db.models import Q
    from django.utils import timezone
    from begunici.app_types.animals.models import ARCHIVE_STATUS_NAMES, Ewe, Lambing, Maker, Ram, Sheep
    from .vet_models import Place

    barn_number = normalize_barn_number(barn_number)
    as_of_date = as_of_date or timezone.localdate()
    composition = empty_composition()
    places = {}
    for place in Place.objects.all():
        match = PLACE_PATTERN.fullmatch(place.sheepfold)
        if match and int(match[1]) == barn_number and int(match[2]) > 0:
            places[place.id] = {"number": int(match[2]), "name": place.sheepfold}
    animals = {}
    for code, model in (("maker", Maker), ("ram", Ram), ("ewe", Ewe), ("sheep", Sheep)):
        animals[code] = list(
            model.objects.filter(is_archived=False, place_id__in=places)
            .exclude(animal_status__status_type__in=ARCHIVE_STATUS_NAMES)
            .select_related("tag", "animal_status")
        )
    latest_lambings = {}
    mother_filter = Q(sheep_id__in=[a.pk for a in animals["sheep"]]) | Q(ewe_id__in=[a.pk for a in animals["ewe"]])
    lambings = (
        Lambing.objects.filter(mother_filter, is_active=False, completion_type=Lambing.COMPLETION_NORMAL,
                               actual_lambing_date__lte=as_of_date, number_of_lambs__gt=0)
        .order_by("-actual_lambing_date", "-id")
        .values("sheep_id", "ewe_id", "actual_lambing_date")
    )
    for lambing in lambings:
        key = ("sheep", lambing["sheep_id"]) if lambing["sheep_id"] else ("ewe", lambing["ewe_id"])
        latest_lambings.setdefault(key, lambing["actual_lambing_date"])
    warnings = []
    total_heads = sum(len(items) for items in animals.values())
    for code, items in animals.items():
        for animal in items:
            status_name = animal.animal_status.status_type if animal.animal_status else None
            group, reason = classify_animal(code, animal.birth_date, status_name, latest_lambings.get((code, animal.pk)), as_of_date)
            section = places[animal.place_id]
            side = "left" if section["number"] % 2 else "right"
            if group is None:
                warnings.append({
                    "tag_number": animal.tag.tag_number, "animal_type": code,
                    "place": section["name"], "reason": reason,
                })
                continue
            composition[group][side] += 1
    return {
        "barn_number": barn_number, "as_of_date": as_of_date.isoformat(),
        "composition": composition, "warnings": warnings,
        "total_heads": total_heads, "classified_heads": total_heads - len(warnings),
        "sections": [
            {**section, "side": "left" if section["number"] % 2 else "right"}
            for section in sorted(places.values(), key=lambda section: section["number"])
        ],
    }
