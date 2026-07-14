from datetime import date
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponse

from .models import Lambing


TEMPLATE_FILENAME = "Akt_osem_i_okot_mec.xlsx"
MONTH_COLUMNS = {
    1: "B",
    2: "C",
    3: "D",
    4: "E",
    5: "F",
    6: "G",
    7: "H",
    8: "I",
    9: "J",
    10: "K",
    11: "L",
    12: "M",
}
INSEMINATION_ROWS = {
    "sheep": 4,
    "ewe": 5,
    "total": 6,
}
LAMBING_ROWS = {
    "sheep": 14,
    "ewe": 15,
    "total": 16,
}
TOTAL_COLUMN = "N"


def get_template_path():
    return (
        Path(settings.BASE_DIR)
        / "begunici"
        / "app_types"
        / "animals"
        / "excel_templates"
        / TEMPLATE_FILENAME
    )


def get_mother_key(lambing):
    """Use the tag where possible so ewe-to-sheep conversion keeps history together."""
    if lambing.sheep_id:
        tag_id = getattr(lambing.sheep, "tag_id", None)
        return ("tag", tag_id) if tag_id else ("sheep", lambing.sheep_id)
    if lambing.ewe_id:
        tag_id = getattr(lambing.ewe, "tag_id", None)
        return ("tag", tag_id) if tag_id else ("ewe", lambing.ewe_id)

    mother_tag = (lambing.mother_tag_text or "").strip().lower()
    if mother_tag:
        return ("text", mother_tag)
    return None


def get_lambing_order_date(lambing):
    return (
        lambing.actual_lambing_date
        or lambing.planned_lambing_date
        or lambing.start_date
        or date.max
    )


def build_first_regular_lambing_ids_by_mother():
    lambings = list(
        Lambing.objects.select_related("sheep__tag", "ewe__tag")
        .exclude(completion_type=Lambing.COMPLETION_EARLY_FAILURE)
    )
    lambings.sort(key=lambda lambing: (get_lambing_order_date(lambing), lambing.id))

    first_ids = {}
    for lambing in lambings:
        mother_key = get_mother_key(lambing)
        if mother_key and mother_key not in first_ids:
            first_ids[mother_key] = lambing.id
    return first_ids


def get_lambing_mother_category(lambing, first_regular_lambing_ids):
    if lambing.mother_category_at_start in {
        Lambing.MOTHER_CATEGORY_SHEEP,
        Lambing.MOTHER_CATEGORY_EWE,
    }:
        return lambing.mother_category_at_start

    mother_key = get_mother_key(lambing)
    if mother_key and first_regular_lambing_ids.get(mother_key) == lambing.id:
        return Lambing.MOTHER_CATEGORY_EWE
    return Lambing.MOTHER_CATEGORY_SHEEP


def empty_month_counts():
    return {
        "sheep": {month: 0 for month in MONTH_COLUMNS},
        "ewe": {month: 0 for month in MONTH_COLUMNS},
    }


def build_monthly_breeding_counts(year):
    first_regular_lambing_ids = build_first_regular_lambing_ids_by_mother()
    counts = {
        "insemination": empty_month_counts(),
        "lambing": empty_month_counts(),
    }

    insemination_lambings = (
        Lambing.objects.filter(start_date__year=year)
        .select_related("sheep__tag", "ewe__tag")
        .order_by("start_date", "id")
    )
    for lambing in insemination_lambings:
        category = get_lambing_mother_category(lambing, first_regular_lambing_ids)
        counts["insemination"][category][lambing.start_date.month] += 1

    completed_lambings = (
        Lambing.objects.filter(
            is_active=False,
            actual_lambing_date__isnull=False,
            actual_lambing_date__year=year,
        )
        .exclude(completion_type=Lambing.COMPLETION_EARLY_FAILURE)
        .select_related("sheep__tag", "ewe__tag")
        .order_by("actual_lambing_date", "id")
    )
    for lambing in completed_lambings:
        category = get_lambing_mother_category(lambing, first_regular_lambing_ids)
        counts["lambing"][category][lambing.actual_lambing_date.month] += 1

    return counts


def fill_monthly_block(sheet, row_map, counts):
    for month, column in MONTH_COLUMNS.items():
        sheep_count = counts["sheep"][month]
        ewe_count = counts["ewe"][month]
        sheet[f"{column}{row_map['sheep']}"] = sheep_count
        sheet[f"{column}{row_map['ewe']}"] = ewe_count
        sheet[f"{column}{row_map['total']}"] = sheep_count + ewe_count

    for row_key in ("sheep", "ewe", "total"):
        row_number = row_map[row_key]
        sheet[f"{TOTAL_COLUMN}{row_number}"] = sum(
            sheet[f"{column}{row_number}"].value or 0
            for column in MONTH_COLUMNS.values()
        )


def generate_monthly_breeding_act_workbook(year):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("Библиотека openpyxl не установлена") from exc

    template_path = get_template_path()
    if not template_path.exists():
        raise FileNotFoundError(f"Шаблон не найден: {template_path}")

    workbook = load_workbook(template_path)
    sheet = workbook.active
    counts = build_monthly_breeding_counts(year)

    sheet["B1"] = year
    sheet["B11"] = year
    fill_monthly_block(sheet, INSEMINATION_ROWS, counts["insemination"])
    fill_monthly_block(sheet, LAMBING_ROWS, counts["lambing"])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def monthly_breeding_act_response(year):
    output = generate_monthly_breeding_act_workbook(year)
    filename = f"akt_osemeneniya_i_okotov_po_mesyacam_{year}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response
