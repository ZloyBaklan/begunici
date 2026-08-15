import calendar
from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

from begunici.app_types.veterinary.vet_models import StatusHistory

from .models import ARCHIVE_STATUS_NAMES, ArchiveAct, Ewe, Lambing, Maker, Ram, Sheep


TEMPLATE_FILENAME = "sp-51.xlsx"

DATA_ROWS = {
    "sheep": 19,
    "maker": 20,
    "ram_current": 21,
    "ram_previous": 22,
    "ram_old": 23,
    "ewe_current": 24,
    "ewe_previous": 25,
    "ewe_old": 26,
    "progeny": 27,
}

ARCHIVE_STATUS_COLUMNS = {
    "Продажа на племя": "AB",
    "Реализация в живом весе": "AD",
    "Вынужденная прирезка": "AF",
    "Убой на мясо": "AH",
    "Падеж": "AJ",
}

ANIMAL_MODELS = (
    ("Maker", Maker),
    ("Ram", Ram),
    ("Ewe", Ewe),
    ("Sheep", Sheep),
)

MONTH_NAMES = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}

MONTH_NAMES_GENITIVE = {
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


def get_template_path():
    return (
        Path(settings.BASE_DIR)
        / "begunici"
        / "app_types"
        / "animals"
        / "excel_templates"
        / TEMPLATE_FILENAME
    )


def month_end_date(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def normalize_date(value):
    if not value:
        return None
    if hasattr(value, "date"):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    return value


def get_report_act_date(year, month):
    today = timezone.localdate()
    period_start = date(year, month, 1)
    period_end = month_end_date(year, month)
    if period_start <= today <= period_end:
        return today
    return period_end


def get_all_animals():
    animals = []
    for animal_type, model in ANIMAL_MODELS:
        queryset = model.objects.select_related("tag", "animal_status").all()
        animals.extend((animal_type, animal) for animal in queryset)
    return animals


def build_status_history_map(tag_ids):
    history_map = defaultdict(list)
    histories = (
        StatusHistory.objects.select_related("new_status")
        .filter(tag_id__in=tag_ids)
        .order_by("tag_id", "change_date", "id")
    )
    for history in histories:
        history_map[history.tag_id].append(history)
    return history_map


def build_archive_dates_map(tag_ids, history_map):
    archive_dates = defaultdict(list)
    for tag_id, histories in history_map.items():
        for history in histories:
            status_name = history.new_status.status_type if history.new_status else ""
            history_date = normalize_date(history.change_date)
            if status_name in ARCHIVE_STATUS_NAMES and history_date:
                archive_dates[tag_id].append(history_date)

    acts = (
        ArchiveAct.objects.filter(tag_id__in=tag_ids, status_date__isnull=False)
        .order_by("tag_id", "-updated_at", "-id")
        .values("tag_id", "status_date")
    )
    for act in acts:
        if act["status_date"] not in archive_dates[act["tag_id"]]:
            archive_dates[act["tag_id"]].append(act["status_date"])

    for tag_id in list(archive_dates.keys()):
        archive_dates[tag_id].sort()

    return archive_dates


def get_status_name_on_date(animal, history_map, as_of_date):
    tag_id = animal.tag_id
    latest_history = None
    for history in history_map.get(tag_id, []):
        history_date = normalize_date(history.change_date)
        if history_date and history_date <= as_of_date:
            latest_history = history
        elif history_date and history_date > as_of_date:
            break

    if latest_history:
        return latest_history.new_status.status_type if latest_history.new_status else ""

    return animal.animal_status.status_type if animal.animal_status else ""


def is_active_on_date(animal, history_map, archive_dates_map, as_of_date):
    if animal.birth_date and animal.birth_date > as_of_date:
        return False

    tag_id = animal.tag_id
    archive_dates = archive_dates_map.get(tag_id, [])
    current_status_name = animal.animal_status.status_type if animal.animal_status else ""

    if animal.is_archived or current_status_name in ARCHIVE_STATUS_NAMES:
        if not archive_dates:
            return False
        if any(archive_date <= as_of_date for archive_date in archive_dates):
            return False
        return True

    latest_history = None
    for history in history_map.get(tag_id, []):
        history_date = normalize_date(history.change_date)
        if history_date and history_date <= as_of_date:
            latest_history = history
        elif history_date and history_date > as_of_date:
            break

    if latest_history:
        status_name = latest_history.new_status.status_type if latest_history.new_status else ""
        return status_name not in ARCHIVE_STATUS_NAMES

    if archive_dates and min(archive_dates) > as_of_date:
        return True

    if archive_dates and min(archive_dates) <= as_of_date:
        return False

    return current_status_name not in ARCHIVE_STATUS_NAMES


def build_sheep_first_lambing_map():
    first_lambings = {}
    lambings = (
        Lambing.objects.select_related("sheep__tag")
        .filter(sheep_id__isnull=False, actual_lambing_date__isnull=False)
        .exclude(completion_type__in=Lambing.NON_PRODUCTIVE_COMPLETION_TYPES)
        .order_by("sheep_id", "actual_lambing_date", "id")
    )
    for lambing in lambings:
        first_lambings.setdefault(lambing.sheep_id, lambing)
    return first_lambings


def was_sheep_ewe_on_date(animal, as_of_date, sheep_first_lambing_map):
    first_lambing = sheep_first_lambing_map.get(animal.id)
    if not first_lambing or not first_lambing.actual_lambing_date:
        return False

    mother_category = first_lambing.mother_category_at_start
    if not mother_category:
        # Legacy fallback matches existing monthly breeding act logic:
        # the first regular lambing of a mother is treated as a first lambing.
        mother_category = Lambing.MOTHER_CATEGORY_EWE

    return (
        mother_category == Lambing.MOTHER_CATEGORY_EWE
        and as_of_date < first_lambing.actual_lambing_date
    )


def is_progeny_by_age(animal, as_of_date):
    if not animal.birth_date:
        return False
    return as_of_date < animal.birth_date + relativedelta(months=7)


def get_year_group(prefix, birth_date, report_year):
    if not birth_date:
        return f"{prefix}_old"
    if birth_date.year == report_year:
        return f"{prefix}_current"
    if birth_date.year == report_year - 1:
        return f"{prefix}_previous"
    return f"{prefix}_old"


def classify_animal_group(animal_type, animal, as_of_date, report_year, sheep_first_lambing_map):
    # Приплод считается первым, чтобы он не попадал в ярки/баранчики по году.
    if is_progeny_by_age(animal, as_of_date):
        return "progeny"

    if animal_type == "Maker":
        return "maker"
    if animal_type == "Ram":
        return get_year_group("ram", animal.birth_date, report_year)
    if animal_type == "Ewe":
        return get_year_group("ewe", animal.birth_date, report_year)
    if animal_type == "Sheep":
        if was_sheep_ewe_on_date(animal, as_of_date, sheep_first_lambing_map):
            return get_year_group("ewe", animal.birth_date, report_year)
        return "sheep"
    return None


def get_archive_events_for_period(tag_ids, history_map, archive_dates_map, period_start, period_end):
    events = []
    seen = set()

    for tag_id in tag_ids:
        for history in history_map.get(tag_id, []):
            status_name = history.new_status.status_type if history.new_status else ""
            history_date = normalize_date(history.change_date)
            if (
                status_name in ARCHIVE_STATUS_NAMES
                and history_date
                and period_start <= history_date <= period_end
            ):
                key = (tag_id, status_name, history_date)
                if key not in seen:
                    seen.add(key)
                    events.append((tag_id, status_name, history_date))

    # Fallback for archived animals that have ArchiveAct/status dates but no matching status object.
    for tag_id, archive_dates in archive_dates_map.items():
        if any(event_tag_id == tag_id for event_tag_id, _, _ in events):
            continue
        for archive_date in archive_dates:
            if period_start <= archive_date <= period_end:
                events.append((tag_id, "", archive_date))
                break

    return events


def increment(counter, group_key, amount=1):
    if group_key:
        counter[group_key] += amount


def build_livestock_movement_group(year, month):
    period_start = date(year, month, 1)
    period_end = month_end_date(year, month)
    act_date = get_report_act_date(year, month)
    effective_period_end = min(period_end, act_date)
    begin_snapshot_date = period_start - timedelta(days=1)

    animals = get_all_animals()
    tag_ids = [animal.tag_id for _, animal in animals if animal.tag_id]
    animal_by_tag_id = {
        animal.tag_id: (animal_type, animal)
        for animal_type, animal in animals
        if animal.tag_id
    }
    history_map = build_status_history_map(tag_ids)
    archive_dates_map = build_archive_dates_map(tag_ids, history_map)
    sheep_first_lambing_map = build_sheep_first_lambing_map()
    archive_events = get_archive_events_for_period(
        tag_ids,
        history_map,
        archive_dates_map,
        period_start,
        effective_period_end,
    )
    archived_tag_ids_in_period = {tag_id for tag_id, _, _ in archive_events}

    counts = {
        "beginning": defaultdict(int),
        "incoming_groups": defaultdict(int),
        "outgoing_groups": defaultdict(int),
        "archive": defaultdict(lambda: defaultdict(int)),
        "ending": defaultdict(int),
    }

    for animal_type, animal in animals:
        if not animal.tag_id:
            continue

        active_at_beginning = is_active_on_date(
            animal,
            history_map,
            archive_dates_map,
            begin_snapshot_date,
        )
        active_at_end = is_active_on_date(
            animal,
            history_map,
            archive_dates_map,
            effective_period_end,
        )

        beginning_group = None
        ending_group = None

        if active_at_beginning and (not animal.birth_date or animal.birth_date <= begin_snapshot_date):
            beginning_group = classify_animal_group(
                animal_type,
                animal,
                begin_snapshot_date,
                year,
                sheep_first_lambing_map,
            )
            increment(counts["beginning"], beginning_group)

        if active_at_end and (not animal.birth_date or animal.birth_date <= effective_period_end):
            ending_group = classify_animal_group(
                animal_type,
                animal,
                effective_period_end,
                year,
                sheep_first_lambing_map,
            )
            increment(counts["ending"], ending_group)

        if animal.birth_date and period_start <= animal.birth_date <= effective_period_end:
            increment(counts["incoming_groups"], "progeny")
            continue

        if animal.tag_id in archived_tag_ids_in_period:
            continue

        if active_at_beginning and active_at_end and beginning_group and ending_group and beginning_group != ending_group:
            increment(counts["outgoing_groups"], beginning_group)
            increment(counts["incoming_groups"], ending_group)

    for tag_id, status_name, archive_date in archive_events:
        animal_info = animal_by_tag_id.get(tag_id)
        if not animal_info:
            continue
        animal_type, animal = animal_info
        archive_group = classify_animal_group(
            animal_type,
            animal,
            archive_date,
            year,
            sheep_first_lambing_map,
        )
        if not status_name:
            status_name = animal.animal_status.status_type if animal.animal_status else ""
        if status_name in ARCHIVE_STATUS_COLUMNS:
            counts["archive"][archive_group][status_name] += 1

    return {
        "year": year,
        "month": month,
        "period_start": period_start,
        "period_end": period_end,
        "effective_period_end": effective_period_end,
        "act_date": act_date,
        "counts": counts,
    }


def set_count_cell(sheet, cell, value, blank_zero=False):
    if blank_zero and not value:
        sheet[cell] = ""
    else:
        sheet[cell] = int(value or 0)


def fill_split_date(sheet, day_cell, month_cell, year_cell, value):
    sheet[day_cell] = f"{value.day:02d}"
    sheet[month_cell] = f"{value.month:02d}"
    sheet[year_cell] = str(value.year)[-2:]


def fill_footer_date(sheet, value):
    sheet["G35"] = f"{value.day:02d}"
    sheet["I35"] = MONTH_NAMES_GENITIVE.get(value.month, f"{value.month:02d}")
    sheet["N35"] = str(value.year)[-2:]


def fill_livestock_movement_sheet(sheet, group):
    counts = group["counts"]

    sheet["S7"] = MONTH_NAMES.get(group["month"], str(group["month"]))
    sheet["W7"] = str(group["year"])[-2:]
    fill_split_date(sheet, "AP8", "AR8", "AT8", group["act_date"])
    fill_footer_date(sheet, timezone.localdate())

    for group_key, row in DATA_ROWS.items():
        beginning_count = counts["beginning"].get(group_key, 0)
        incoming_count = counts["incoming_groups"].get(group_key, 0)
        outgoing_count = counts["outgoing_groups"].get(group_key, 0)
        archive_total = sum(counts["archive"].get(group_key, {}).values())
        ending_count = counts["ending"].get(group_key, 0)

        set_count_cell(sheet, f"C{row}", beginning_count)
        set_count_cell(sheet, f"I{row}", incoming_count, blank_zero=True)
        set_count_cell(sheet, f"V{row}", outgoing_count, blank_zero=True)

        for status_name, column in ARCHIVE_STATUS_COLUMNS.items():
            set_count_cell(
                sheet,
                f"{column}{row}",
                counts["archive"].get(group_key, {}).get(status_name, 0),
                blank_zero=True,
            )

        set_count_cell(sheet, f"R{row}", incoming_count, blank_zero=True)
        set_count_cell(sheet, f"AM{row}", outgoing_count + archive_total, blank_zero=True)
        set_count_cell(sheet, f"AQ{row}", ending_count)

        # Весовые колонки в СП-51 пока намеренно не заполняем.
        for column in ("F", "J", "L", "N", "P", "Q", "S", "U", "X", "AA", "AC", "AE", "AG", "AI", "AK", "AN", "AS"):
            sheet[f"{column}{row}"] = ""


def generate_livestock_movement_act_workbook(year, month):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("Библиотека openpyxl не установлена") from exc

    template_path = get_template_path()
    if not template_path.exists():
        raise FileNotFoundError(f"Шаблон СП-51 не найден: {template_path}")

    group = build_livestock_movement_group(year, month)
    workbook = load_workbook(template_path)
    sheet = workbook.active
    fill_livestock_movement_sheet(sheet, group)

    if hasattr(workbook, "calculation"):
        workbook.calculation.fullCalcOnLoad = True
        workbook.calculation.forceFullCalc = True

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output, group


def livestock_movement_act_response(year, month):
    output, group = generate_livestock_movement_act_workbook(year, month)
    filename = f"otchet_dvizhenie_skota_sp51_{year}_{month:02d}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response
