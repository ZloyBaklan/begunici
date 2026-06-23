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
        "reason": "падеж",
        "row": 15,
    },
    "Вынужденная прирезка": {
        "filename": "zaboi.xlsx",
        "reason": "забой",
        "row": 15,
    },
    "Реализация в живом весе": {
        "filename": "prirezka.xlsx",
        "reason": "прирезка",
        "row": 17,
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


def get_latest_live_weight(tag):
    record = WeightRecord.objects.filter(tag=tag).order_by("-weight_date", "-id").first()
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
        return "0 дн."

    delta = relativedelta(reference_date, birth_date)
    total_months = delta.years * 12 + delta.months

    if total_months == 0:
        days = (reference_date - birth_date).days
        return f"{days} дн."
    if total_months < 24:
        return f"{total_months} мес."
    if delta.months == 0:
        return f"{delta.years} л."
    return f"{delta.years} г. {delta.months} мес."


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


def build_archive_act_preview_item(animal, status_name=None):
    status_name = status_name or (animal.animal_status.status_type if animal.animal_status else "")
    archive_date = get_archive_status_date(animal) or timezone.now().date()
    live_weight = get_latest_live_weight(animal.tag)
    animal_type = animal.get_animal_type()
    return {
        "animal_type": animal_type,
        "animal_type_label": ANIMAL_TYPE_LABELS.get(animal_type, animal_type),
        "tag_number": animal.tag.tag_number if animal.tag else "",
        "display_name": animal.get_display_name() if hasattr(animal, "get_display_name") else str(animal.tag),
        "sex": ANIMAL_SEX_LABELS.get(animal_type, ""),
        "age": format_age_for_act(animal.birth_date, archive_date),
        "live_weight": format_weight_value(live_weight),
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


def get_archive_act_context(animal):
    status_name = animal.animal_status.status_type if animal.animal_status else ""
    config = get_archive_act_template_config(status_name)
    if not config:
        return None

    act = get_archive_act_for_animal(animal)
    status_date = (act.status_date if act else None) or get_archive_status_date(animal)
    live_weight = (act.live_weight if act and act.live_weight is not None else None) or get_latest_live_weight(animal.tag)
    animal_type = animal.get_animal_type()

    return {
        "config": config,
        "status_name": status_name,
        "status_date": status_date,
        "act_number": (act.act_number if act else "") or get_act_number_from_note(animal.note),
        "act_date": act.act_date if act else None,
        "live_weight": live_weight,
        "fatness": (act.fatness if act else "") or "",
        "diagnosis": (act.diagnosis if act else "") or "",
        "worker_name": (act.worker_name if act else "") or "",
        "animal_group": "овцы",
        "animal_identifier": animal.get_display_name() if hasattr(animal, "get_display_name") else animal.tag.tag_number,
        "sex": ANIMAL_SEX_LABELS.get(animal_type, ""),
        "age": format_age_for_act(animal.birth_date, status_date),
    }


def write_date_parts(sheet, date_value):
    date_value = normalize_date(date_value)
    if not date_value:
        return
    sheet["G33"] = f"{date_value.day:02d}"
    sheet["I33"] = RUSSIAN_MONTHS_GENITIVE.get(date_value.month, "")
    sheet["P33"] = str(date_value.year)[-2:]


def write_status_date_parts(sheet, date_value):
    date_value = normalize_date(date_value)
    if not date_value:
        return
    sheet["AN7"] = f"{date_value.day:02d}"
    sheet["AO7"] = f"{date_value.month:02d}"
    sheet["AP7"] = str(date_value.year)[-2:]


def generate_archive_act_workbook(animal):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("Библиотека openpyxl не установлена") from exc

    context = get_archive_act_context(animal)
    if not context:
        return None

    template_path = get_archive_act_template_path(context["status_name"])
    if not template_path or not template_path.exists():
        raise FileNotFoundError(f"Шаблон акта не найден: {template_path}")

    workbook = load_workbook(template_path)
    sheet = workbook.active
    row = context["config"]["row"]

    sheet["AA4"] = context["act_number"] or ""
    write_status_date_parts(sheet, context["status_date"])

    sheet[f"A{row}"] = context["animal_group"]
    sheet[f"G{row}"] = context["animal_identifier"]
    sheet[f"M{row}"] = context["sex"]
    sheet[f"N{row}"] = context["age"]
    sheet[f"Q{row}"] = context["fatness"]
    sheet[f"T{row}"] = 1
    sheet[f"U{row}"] = format_weight_value(context["live_weight"])
    sheet[f"AE{row}"] = context["config"]["reason"]
    sheet[f"AH{row}"] = context["diagnosis"]
    sheet[f"AJ{row}"] = context["worker_name"]

    write_date_parts(sheet, context["act_date"])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def archive_act_response(animal):
    output = generate_archive_act_workbook(animal)
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
