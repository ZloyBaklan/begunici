from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

from begunici.app_types.veterinary.vet_models import StatusHistory, Tag, WeightRecord

from .models import ArchiveAct, Ewe, Maker, Ram, Sheep


ARCHIVE_ACT_TEMPLATES = {
    "Падеж": {
        "filename": "padej.xlsx",
        "reason": "Падеж",
        "row": 15,
        "layout": "standard",
    },
    "Вынужденная прирезка": {
        "filename": "zaboi.xlsx",
        "reason": "Забой (Вынужденная прирезка)",
        "row": 15,
        "layout": "standard",
    },
    "Убой на мясо": {
        "filename": "prirezka.xlsx",
        "reason": "Прирезка (Убой на мясо)",
        "row": 15,
        "layout": "standard",
    },
    "Реализация в живом весе": {
        "filename": "prodaja.xlsx",
        "reason": "Реализация в живом весе",
        "row": 20,
        "layout": "sale",
    },
    "Продажа на племя": {
        "filename": "prodaja.xlsx",
        "reason": "Продажа на племя",
        "row": 20,
        "layout": "sale",
    },
}

ANIMAL_TYPE_MODELS = {
    "maker": Maker,
    "Maker": Maker,
    "ram": Ram,
    "Ram": Ram,
    "ewe": Ewe,
    "Ewe": Ewe,
    "sheep": Sheep,
    "Sheep": Sheep,
}

ANIMAL_TYPE_LABELS = {
    "Maker": "Баран-Производитель",
    "Ram": "Баранчик",
    "Ewe": "Ярка",
    "Sheep": "Овцематка",
}

ANIMAL_SEX_LABELS = {
    "Maker": "баран",
    "Ram": "баранчик",
    "Ewe": "ярка",
    "Sheep": "овцематка",
}

RUSSIAN_MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

RESPONSIBLE_PERSON_BY_USERNAME = {
    "main": "Гришин А.Е.",
}


def normalize_date(value):
    if not value:
        return None
    if hasattr(value, "date"):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    return value


def get_archive_act_template_config(status_name):
    return ARCHIVE_ACT_TEMPLATES.get(status_name or "")


def get_archive_act_template_path(status_name):
    config = get_archive_act_template_config(status_name)
    if not config:
        return None
    return (
        Path(settings.BASE_DIR)
        / "begunici"
        / "app_types"
        / "animals"
        / "excel_templates"
        / "archive_acts"
        / config["filename"]
    )


def find_animal(animal_type, tag_number):
    model = ANIMAL_TYPE_MODELS.get(animal_type)
    if not model:
        return None
    try:
        return model.objects.select_related("tag", "animal_status", "place").get(tag__tag_number=tag_number)
    except model.DoesNotExist:
        return None


def get_latest_live_weight_record(tag):
    record = WeightRecord.objects.filter(tag=tag).order_by("-weight_date", "-id").first()
    return record


def get_latest_live_weight(tag):
    record = get_latest_live_weight_record(tag)
    return record.weight if record else None


def get_archive_status_date(animal):
    if not animal.tag or not animal.animal_status:
        return None
    history = (
        StatusHistory.objects.filter(tag=animal.tag, new_status=animal.animal_status)
        .order_by("-change_date", "-id")
        .first()
    )
    if history and history.change_date:
        return normalize_date(history.change_date)
    return None


def format_age_for_act(birth_date, reference_date=None):
    if not birth_date:
        return ""
    reference_date = reference_date or timezone.now().date()
    if hasattr(reference_date, "date"):
        reference_date = reference_date.date()
    if reference_date < birth_date:
        return "0 мес. (0 сут.)"

    delta = relativedelta(reference_date, birth_date)
    total_months = delta.years * 12 + delta.months
    remaining_days = delta.days

    return f"{total_months} мес. ({remaining_days} сут.)"


def get_responsible_person_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    return RESPONSIBLE_PERSON_BY_USERNAME.get(getattr(user, "username", ""), "")


def format_weight_value(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if number.is_integer():
        return int(number)
    return round(number, 1)


def format_weight_display(value):
    formatted = format_weight_value(value)
    if formatted is None:
        return "-"
    return f"{formatted} кг"


def format_weight_record_display(record):
    if not record:
        return "-"
    return f"{record.weight_date.strftime('%d.%m.%Y')}: {format_weight_display(record.weight)}"


def build_archive_act_preview_item(animal, status_name=None):
    status_name = status_name or (animal.animal_status.status_type if animal.animal_status else "")
    archive_date = get_archive_status_date(animal) or timezone.now().date()
    latest_weight_record = get_latest_live_weight_record(animal.tag)
    live_weight = latest_weight_record.weight if latest_weight_record else None
    animal_type = animal.get_animal_type()
    return {
        "animal_type": animal_type,
        "animal_type_label": ANIMAL_TYPE_LABELS.get(animal_type, animal_type),
        "tag_number": animal.tag.tag_number if animal.tag else "",
        "display_name": animal.get_display_name() if hasattr(animal, "get_display_name") else str(animal.tag),
        "sex": ANIMAL_SEX_LABELS.get(animal_type, ""),
        "age": format_age_for_act(animal.birth_date, archive_date),
        "live_weight": format_weight_value(live_weight),
        "latest_weight_date": latest_weight_record.weight_date.strftime("%Y-%m-%d") if latest_weight_record else None,
        "latest_weight_display": format_weight_record_display(latest_weight_record),
        "status_name": status_name,
        "reason": get_archive_act_template_config(status_name)["reason"] if get_archive_act_template_config(status_name) else "",
    }


def get_archive_act_for_animal(animal):
    if not animal.tag:
        return None
    return animal.tag.archive_acts.order_by("-updated_at", "-id").first()


def get_act_number_from_note(note):
    if not note:
        return ""
    first_line = str(note).splitlines()[0].strip()
    prefix = "Номер акта:"
    if first_line.startswith(prefix):
        return first_line.replace(prefix, "", 1).strip()
    return ""


def get_archive_act_context(animal, user=None):
    status_name = animal.animal_status.status_type if animal.animal_status else ""
    config = get_archive_act_template_config(status_name)
    if not config:
        return None

    act = get_archive_act_for_animal(animal)
    status_date = (act.status_date if act else None) or get_archive_status_date(animal)
    live_weight = (act.live_weight if act and act.live_weight is not None else None) or get_latest_live_weight(animal.tag)
    animal_type = animal.get_animal_type()
    responsible_person = get_responsible_person_for_user(user)

    return {
        "config": config,
        "status_name": status_name,
        "status_date": status_date,
        "act_number": (act.act_number if act else "") or get_act_number_from_note(animal.note),
        "act_date": act.act_date if act else None,
        "live_weight": live_weight,
        "fatness": (act.fatness if act else "") or "",
        "diagnosis": (act.diagnosis if act else "") or "",
        "responsible_person": responsible_person or (act.worker_name if act else "") or "",
        "animal_group": "овцы",
        "animal_identifier": animal.get_display_name() if hasattr(animal, "get_display_name") else animal.tag.tag_number,
        "sex": ANIMAL_SEX_LABELS.get(animal_type, ""),
        "age": format_age_for_act(animal.birth_date, status_date),
    }


def write_date_parts(sheet, date_value, cells=("G27", "I27", "P27")):
    date_value = normalize_date(date_value)
    if not date_value:
        return
    day_cell, month_cell, year_cell = cells
    sheet[day_cell] = f"{date_value.day:02d}"
    sheet[month_cell] = RUSSIAN_MONTHS_GENITIVE.get(date_value.month, "")
    sheet[year_cell] = str(date_value.year)[-2:]


def write_status_date_parts(sheet, date_value, cells=("AN7", "AO7", "AP7")):
    date_value = normalize_date(date_value)
    if not date_value:
        return
    day_cell, month_cell, year_cell = cells
    sheet[day_cell] = f"{date_value.day:02d}"
    sheet[month_cell] = f"{date_value.month:02d}"
    sheet[year_cell] = str(date_value.year)[-2:]


def write_act_number(sheet, context):
    act_number = context["act_number"] or ""
    if context["config"].get("layout") == "sale":
        sheet["G1"] = f"АКТ  № {act_number}" if act_number else "АКТ  № ______"
        return
    sheet["AA4"] = act_number


def write_archive_sender(sheet, context):
    responsible_person = context.get("responsible_person") or ""
    if context["config"].get("layout") == "sale":
        sheet["F15"] = responsible_person
        return
    sheet["F11"] = responsible_person


def write_archive_act_row(sheet, context):
    row = context["config"]["row"]
    weight_value = format_weight_value(context["live_weight"])

    if context["config"].get("layout") == "sale":
        sheet[f"A{row}"] = context["animal_group"]
        sheet[f"C{row}"] = context["animal_identifier"]
        sheet[f"J{row}"] = context["sex"]
        sheet[f"K{row}"] = context["age"]
        sheet[f"L{row}"] = context["fatness"]
        sheet[f"O{row}"] = 1
        sheet[f"S{row}"] = weight_value
        sheet[f"Z{row}"] = context["config"]["reason"]
        sheet[f"AA{row}"] = context["diagnosis"]
        sheet[f"AI{row}"] = context.get("responsible_person") or ""
        return

    sheet[f"A{row}"] = context["animal_group"]
    sheet[f"G{row}"] = context["animal_identifier"]
    sheet[f"M{row}"] = context["sex"]
    sheet[f"N{row}"] = context["age"]
    sheet[f"Q{row}"] = context["fatness"]
    sheet[f"T{row}"] = 1
    sheet[f"U{row}"] = weight_value
    sheet[f"AE{row}"] = context["config"]["reason"]
    sheet[f"AH{row}"] = context["diagnosis"]
    sheet[f"AJ{row}"] = context.get("responsible_person") or ""


def generate_archive_act_workbook(animal, user=None):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("Библиотека openpyxl не установлена") from exc

    context = get_archive_act_context(animal, user=user)
    if not context:
        return None

    template_path = get_archive_act_template_path(context["status_name"])
    if not template_path or not template_path.exists():
        raise FileNotFoundError(f"Шаблон акта не найден: {template_path}")

    workbook = load_workbook(template_path)
    sheet = workbook.active

    write_act_number(sheet, context)
    write_archive_sender(sheet, context)
    if context["config"].get("layout") == "sale":
        write_status_date_parts(sheet, context["status_date"], cells=("AO8", "AQ8", "AR8"))
        write_archive_act_row(sheet, context)
        write_date_parts(sheet, context["act_date"], cells=("G34", "I34", "P34"))
    else:
        write_status_date_parts(sheet, context["status_date"])
        write_archive_act_row(sheet, context)
        write_date_parts(sheet, context["act_date"])


    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def archive_act_response(animal, user=None):
    output = generate_archive_act_workbook(animal, user=user)
    if output is None:
        return None

    tag_number = animal.tag.tag_number if animal.tag else "animal"
    status_name = animal.animal_status.status_type if animal.animal_status else "act"
    filename = f"act_{status_name}_{tag_number}.xlsx".replace(" ", "_")
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response
