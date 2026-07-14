from calendar import monthrange
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

from .models import Ewe, Maker, Ram, Sheep


TEMPLATE_FILENAME = "korm_plan.xlsx"
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
FEED_GROUP_ROWS = {
    "makers": 10,
    "pregnant_females": 11,
    "lactating_females": 12,
    "young_3_to_6_months": 13,
    "young_7_to_12_months": 14,
    "young_under_3_months": 15,
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


def get_full_age_months(birth_date, as_of_date):
    if not birth_date or birth_date > as_of_date:
        return None

    delta = relativedelta(as_of_date, birth_date)
    return delta.years * 12 + delta.months


def count_active_females_by_status(status_name):
    filters = {
        "is_archived": False,
        "animal_status__status_type": status_name,
    }
    return Ewe.objects.filter(**filters).count() + Sheep.objects.filter(**filters).count()


def build_young_age_counts(as_of_date):
    counts = {
        "young_under_3_months": 0,
        "young_3_to_6_months": 0,
        "young_7_to_12_months": 0,
    }

    birth_dates = []
    for model in (Ram, Ewe):
        birth_dates.extend(
            model.objects.filter(is_archived=False, birth_date__isnull=False)
            .values_list("birth_date", flat=True)
        )

    for birth_date in birth_dates:
        age_months = get_full_age_months(birth_date, as_of_date)
        if age_months is None:
            continue

        if age_months < 3:
            counts["young_under_3_months"] += 1
        elif 3 <= age_months <= 6:
            counts["young_3_to_6_months"] += 1
        elif 7 <= age_months <= 12:
            counts["young_7_to_12_months"] += 1

    return counts


def build_feed_plan_counts(as_of_date):
    counts = {
        "makers": Maker.objects.filter(is_archived=False).count(),
        "pregnant_females": count_active_females_by_status("Суягная"),
        "lactating_females": count_active_females_by_status("Лактирующая"),
    }
    counts.update(build_young_age_counts(as_of_date))
    return counts


def fill_feed_plan_workbook(workbook, as_of_date=None):
    as_of_date = as_of_date or timezone.localdate()
    month_name = MONTH_NAMES[as_of_date.month]
    days_in_month = monthrange(as_of_date.year, as_of_date.month)[1]
    counts = build_feed_plan_counts(as_of_date)

    sheet = workbook.active
    sheet.title = f"кормовой план {month_name}"
    sheet["B3"] = f"     на {month_name}"
    sheet["E3"] = f"{as_of_date.year} г."

    for row_number in FEED_GROUP_ROWS.values():
        sheet[f"C{row_number}"] = days_in_month

    for group_key, row_number in FEED_GROUP_ROWS.items():
        sheet[f"B{row_number}"] = counts[group_key]

    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    return workbook


def generate_feed_plan_workbook(as_of_date=None):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("Библиотека openpyxl не установлена") from exc

    template_path = get_template_path()
    if not template_path.exists():
        raise FileNotFoundError(f"Шаблон не найден: {template_path}")

    workbook = load_workbook(template_path)
    fill_feed_plan_workbook(workbook, as_of_date=as_of_date)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def feed_plan_response(as_of_date=None):
    as_of_date = as_of_date or timezone.localdate()
    output = generate_feed_plan_workbook(as_of_date=as_of_date)
    filename = f"kormovoy_plan_{as_of_date.year}_{as_of_date.month:02d}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response
