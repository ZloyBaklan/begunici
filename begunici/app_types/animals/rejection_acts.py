from collections import defaultdict
from copy import copy
from io import BytesIO
from pathlib import Path
from textwrap import wrap

from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import load_workbook
from openpyxl.styles import Alignment

from begunici.app_types.veterinary.vet_models import WeightRecord

from .archive_acts import ANIMAL_TYPE_LABELS
from .models import AnimalRejectionHistory, Ewe, Maker, Ram, Sheep, SheepBodyConditionRecord
from .progeny_acts import adjust_merged_cells_for_insert, copy_data_row_merges, copy_row_style
from .transfer_acts import parse_filter_date, parse_filter_int


DATA_START_ROW = 35
TOTAL_ROW = 40
LAST_ROW = 55
DATA_COLUMNS = ("A", "G", "AO", "BG", "BY", "CQ", "DK", "EE")


def get_template_path():
    return Path(settings.BASE_DIR) / "begunici/app_types/animals/excel_templates/406-apk.xlsx"


def build_rejection_act_groups(numbered=True):
    events = (
        AnimalRejectionHistory.objects.filter(new_is_reject=True, change_date__isnull=False)
        .select_related("tag")
        .order_by("change_date", "id")
    )
    days = defaultdict(dict)
    for event in events:
        # Keep historical assignments, even after unmarking, retagging or archiving.
        act_date = timezone.localdate(event.change_date)
        days[act_date][event.tag_id] = event

    groups = [
        {
            "act_number": number,
            "act_date": act_date,
            "events": sorted(days[act_date].values(), key=lambda e: (e.tag.tag_number.casefold(), e.tag_id)),
        }
        for number, act_date in enumerate(sorted(days), start=1)
    ]
    if numbered:
        from .act_numbering import number_groups
        number_groups("rejection", groups)
    return groups


def get_rejection_acts_page(page_number=1, page_size=10, act_date=None, month=None, year=None):
    groups = build_rejection_act_groups()
    years = sorted({group["act_date"].year for group in groups}, reverse=True)
    act_date = parse_filter_date(act_date)
    month = parse_filter_int(month, 1, 12)
    year = parse_filter_int(year, 1, 9999)
    filtered = [
        group for group in reversed(groups)
        if (not act_date or group["act_date"] == act_date)
        and (not month or group["act_date"].month == month)
        and (not year or group["act_date"].year == year)
    ]
    page = Paginator(filtered, page_size).get_page(page_number)
    return {
        "count": page.paginator.count,
        "page": page.number,
        "next": page.next_page_number() if page.has_next() else None,
        "previous": page.previous_page_number() if page.has_previous() else None,
        "years": years,
        "unknown_date_count": AnimalRejectionHistory.objects.filter(
            new_is_reject=True, change_date__isnull=True,
        ).count(),
        "results": [
            {
                "act_number": group.get("display_number", group["act_number"]),
                "act_id": group["act_number"],
                "act_date": group["act_date"].isoformat(),
                "animal_count": len(group["events"]),
            }
            for group in page.object_list
        ],
    }


def get_rejection_act_group(act_number):
    return next((group for group in build_rejection_act_groups() if group["act_number"] == act_number), None)


def get_act_animals(events):
    tag_ids = [event.tag_id for event in events]
    candidates = defaultdict(dict)
    for model in (Sheep, Ewe, Ram, Maker):
        fields = ["tag_id", "birth_date"] + (["name"] if model is Maker else [])
        for animal in model.objects.filter(tag_id__in=tag_ids).values(*fields):
            candidates[animal["tag_id"]][model.__name__] = animal
    animals = {}
    for event in events:
        models = candidates[event.tag_id]
        animals[event.tag_id] = models.get(event.tag.animal_type) or next(iter(models.values()), {})
    return animals


def latest_records_at_date(model, tag_ids, date_field, act_date):
    records = (
        model.objects.filter(tag_id__in=tag_ids, **{f"{date_field}__lte": act_date})
        .order_by("tag_id", f"-{date_field}", "-id")
        .distinct("tag_id")
    )
    return {record.tag_id: record for record in records}


def build_rejection_act_rows(group):
    animals = get_act_animals(group["events"])
    act_date = group["act_date"]
    weights = latest_records_at_date(WeightRecord, animals, "weight_date", act_date)
    conditions = latest_records_at_date(SheepBodyConditionRecord, animals, "measurement_date", act_date)
    rows = []
    for event in group["events"]:
        animal = animals[event.tag_id]
        birth_date = animal.get("birth_date")
        age_years = (
            round((act_date - birth_date).days / 365.25, 2)
            if birth_date and birth_date <= act_date else None
        )
        name = animal.get("name")
        identifier = f"{name} ({event.tag.tag_number})" if name else event.tag.tag_number
        weight = weights.get(event.tag_id)
        condition = conditions.get(event.tag_id)
        weight_display = ""
        if weight:
            value = format(weight.weight, "f").rstrip("0").rstrip(".").replace(".", ",")
            weight_display = f"{value} ({weight.weight_date:%d.%m.%Y})"
        rows.append({
            "identifier": identifier,
            "age_years": age_years,
            "sex": ANIMAL_TYPE_LABELS.get(event.animal_type, ""),
            "condition": condition.condition_index if condition else None,
            "weight_display": weight_display,
            "weight": weight.weight if weight else None,
            "reason": event.reason,
        })
    return rows


def set_cell_value(sheet, coordinate, value):
    cell = sheet[coordinate]
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"


def generate_rejection_act_workbook(group):
    workbook = load_workbook(get_template_path())
    sheet = workbook.active
    rows = build_rejection_act_rows(group)
    extra_rows = max(0, len(rows) - (TOTAL_ROW - DATA_START_ROW))
    if extra_rows:
        adjust_merged_cells_for_insert(sheet, TOTAL_ROW, extra_rows)
        for row in range(TOTAL_ROW, TOTAL_ROW + extra_rows):
            copy_row_style(sheet, TOTAL_ROW - 1, row)
            copy_data_row_merges(sheet, TOTAL_ROW - 1, row)

    sheet["CG1"] = group.get("display_number", group["act_number"])
    sheet["CG1"].alignment = Alignment(horizontal="center", vertical="center")
    for cell, value in zip(("BW7", "CC7", "CI7"), (
        f"{group['act_date'].day:02d}", f"{group['act_date'].month:02d}", str(group["act_date"].year),
    )):
        set_cell_value(sheet, cell, value)
        sheet[cell].alignment = Alignment(horizontal="center", vertical="center")

    for row_number, item in enumerate(rows, start=DATA_START_ROW):
        values = (
            row_number - DATA_START_ROW + 1, item["identifier"], item["age_years"],
            item["sex"], item["condition"], item["weight_display"], None, item["reason"],
        )
        for column, value in zip(DATA_COLUMNS, values):
            coordinate = f"{column}{row_number}"
            set_cell_value(sheet, coordinate, value)
            alignment = copy(sheet[coordinate].alignment)
            alignment.wrap_text = True
            alignment.vertical = "center"
            sheet[coordinate].alignment = alignment
        sheet[f"AO{row_number}"].number_format = "0.00"
        reason_lines = sum(max(1, len(wrap(line, width=40))) for line in item["reason"].splitlines())
        sheet.row_dimensions[row_number].height = max(36, min(409, reason_lines * 12))

    total_row = TOTAL_ROW + extra_rows
    known_weights = [item["weight"] for item in rows if item["weight"] is not None]
    sheet[f"CQ{total_row}"] = float(sum(known_weights)) if known_weights else None
    sheet[f"CQ{total_row}"].number_format = "0.00"
    sheet.print_area = f"A1:FE{LAST_ROW + extra_rows}"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.page_setup.scale = None
    sheet.print_options.gridLines = False
    sheet.print_options.headings = False
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def rejection_act_response(act_number):
    group = get_rejection_act_group(act_number)
    if group is None:
        return None
    content = generate_rejection_act_workbook(group)
    response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    filename = f"culling_406_apk_{group.get('display_number', act_number)}_{group['act_date'].isoformat()}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
