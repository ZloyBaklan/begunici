"""Export adapters use the project's existing openpyxl/template convention.

The source workbooks are only read. Every generated version is a separate byte
stream and is frozen in DocumentVersion before the user can approve it.
"""
from collections import defaultdict
from copy import copy
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import Product


def text_cell(sheet, row, column, value):
    cell = sheet.cell(row, column, value)
    if isinstance(value, str):
        cell.data_type = "s"  # User-entered strings never become Excel formulas.
    return cell


def table_sheet(workbook, name, headers, rows):
    sheet = workbook.create_sheet(name)
    for column, title in enumerate(headers, 1):
        cell = text_cell(sheet, 1, column, title)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="285A47")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        sheet.column_dimensions[get_column_letter(column)].width = 23 if column < 5 else 32
    sheet.row_dimensions[1].height = 32
    for row_index, values in enumerate(rows, 2):
        for column, value in enumerate(values, 1):
            cell = text_cell(sheet, row_index, column, value)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if isinstance(value, (float, Decimal)):
                cell.number_format = '#,##0.000'
        sheet.row_dimensions[row_index].height = 34
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_title_rows = "1:1"
    sheet.print_options.horizontalCentered = True
    return sheet


def numeric(value):
    return Decimal(str(value)) if value not in (None, "") else None


def generate_document(document):
    if document.kind == "sp55":
        workbook = slaughter_workbook(document)
    elif document.kind == "sp54":
        workbook = live_workbook(document)
    else:
        workbook = invoice_workbook(document)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _write_slaughter_output_rows(sheet, meat_rows, offal_rows, meat_weight, offal_weight):
    rows = [(name, weight, False) for name, weight in meat_rows]
    if not rows:
        rows.append(("Мясо", Decimal(0), False))
    rows.extend([
        ("Итого мясо", meat_weight, True),
        ("Субпродукты по видам:", None, False),
    ])
    for name, items in offal_rows.items():
        rows.extend((f"{name} ({tag})", weight, False) for tag, weight in items)
        rows.append((f"Итого {name.lower()}", sum((weight for _, weight in items), Decimal(0)), True))
    rows.append(("Итого субпродукты", offal_weight, True))

    styles = {column: copy(sheet.cell(19, column)._style) for column in range(17, 33)}
    extra_rows = max(0, len(rows) - 9)
    # Inserting cells alone does not move merged ranges or row dimensions.
    footer_merges = [copy(merged) for merged in sheet.merged_cells.ranges if merged.min_row >= 25]
    body_merges = [str(merged) for merged in sheet.merged_cells.ranges
                   if merged.min_row >= 16 and merged.max_row <= 24 and merged.min_col >= 17]
    for merged in body_merges:
        sheet.unmerge_cells(merged)
    if extra_rows:
        footer_dimensions = [(index, copy(dimension)) for index, dimension in sheet.row_dimensions.items() if index >= 25]
        for merged in footer_merges:
            sheet.unmerge_cells(str(merged))
        for index, _ in footer_dimensions:
            del sheet.row_dimensions[index]
        sheet.insert_rows(25, amount=extra_rows)
        for index, dimension in footer_dimensions:
            dimension.index = index + extra_rows
            sheet.row_dimensions[dimension.index] = dimension
        for merged in footer_merges:
            merged.shift(row_shift=extra_rows)
            sheet.merge_cells(str(merged))

    for row_index in range(16, 25 + extra_rows):
        for column, style in styles.items():
            cell = sheet.cell(row_index, column)
            cell.value = None
            cell._style = copy(style)
        for first_column, last_column in ((18, 21), (22, 23), (25, 28), (29, 32)):
            sheet.merge_cells(start_row=row_index, start_column=first_column,
                              end_row=row_index, end_column=last_column)
        sheet.row_dimensions[row_index].height = max(sheet.row_dimensions[row_index].height or 0, 30)
    for row_index, (name, weight, is_total) in enumerate(rows, 16):
        label = text_cell(sheet, row_index, 18, name)
        label.alignment = Alignment(wrap_text=True, vertical="center")
        font = copy(label.font)
        font.bold = is_total
        label.font = font
        sheet.cell(row_index, 24, weight)
        # Leave enough height for long product names and identifiers, without shrinking text.
        sheet.row_dimensions[row_index].height = max(30, ((len(name) + 17) // 18) * 12 + 6)
    total_row = 25 + extra_rows
    total_label = text_cell(sheet, total_row, 18, "Итого мясо и субпродукты")
    total_label.alignment = Alignment(wrap_text=True, vertical="center")
    total_font = copy(total_label.font)
    total_font.bold = True
    total_label.font = total_font
    sheet.row_dimensions[total_row].height = max(sheet.row_dimensions[total_row].height or 0, 42)
    sheet.cell(total_row, 24, meat_weight + offal_weight)
    for row_index in [*range(16, total_row), total_row]:
        sheet.cell(row_index, 24).number_format = '#,##0.000'
        sheet.cell(row_index, 24).alignment = Alignment(horizontal="center", vertical="center")
    sheet.print_area = f"A1:AF{33 + extra_rows}"
    sheet.print_title_rows = "1:15"
    sheet.page_setup.fitToHeight = 0


def slaughter_workbook(document):
    template = Path(settings.BASE_DIR) / "begunici/app_types/animals/excel_templates/non_auto/СП-55.xlsx"
    workbook = load_workbook(template)
    sheet = workbook.worksheets[0]
    sheet["K3"] = f"УЧЕТНЫЙ ЛИСТ № {document.number or document.pk}"
    sheet["AD6"] = document.date
    sheet["AD6"].number_format = "dd.mm.yyyy"
    sheet.column_dimensions["AD"].width = max(sheet.column_dimensions["AD"].width or 0, 12)
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 1
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet["E8"] = "Убойный цех"
    sheet["F9"] = "См. строки животных и приложение"
    sheet["V12"] = "Склад продукции"
    sheet["X12"] = "Убойный цех"
    sheet["J28"] = "Овец в живой массе принял"
    workbook.worksheets[1]["B14"] = "Убой овец указанной массы и выход"
    animals = list(document.animals.all())
    animal_rows = []
    for case in animals:
        details = document.payload.get("animals", {}).get(str(case.pk), {})
        conclusion = "; ".join(filter(None, [details.get("fatness", ""), details.get("comment", "")]))
        animal_rows.append([
            case.tag_number, case.snapshot.get("place", ""), 1,
            numeric(details.get("weight")), conclusion,
        ])
    # Fixed source form has 8 rows. All per-animal data remains in the attached
    # dynamic table; overflow is summarized instead of cutting records off.
    groups = defaultdict(list)
    for item in animal_rows:
        groups[item[1]].append(item)
    display = list(groups.items())
    if len(display) > 8:
        display = [("Все участки — см. приложение", animal_rows)]
    for index, (place, members) in enumerate(display):
        row = 16 + index
        text_cell(sheet, row, 5, place)
        sheet[f"H{row}"] = len(members)
        sheet[f"I{row}"] = sum((member[3] or Decimal(0) for member in members), Decimal(0))
        target = "J15" if row == 16 else f"J{row}"
        text_cell(sheet, sheet[target].row, sheet[target].column,
                  "; ".join(f"{member[0]}: {member[4]}" for member in members))
        sheet[target].alignment = Alignment(wrap_text=True, vertical="top")
    sheet["H25"] = len(animals)
    sheet["H26"] = len(animals)
    sheet["I25"] = sum((row[3] or Decimal(0) for row in animal_rows), Decimal(0))
    sheet["I26"] = sheet["I25"].value
    products = {p.code: p for p in Product.objects.all()}
    case_map = {case.pk: case for case in animals}
    outputs, rejected = [], []
    totals = defaultdict(Decimal)
    offal = defaultdict(list)
    meat_by_animal = defaultdict(Decimal)
    for item in document.payload.get("outputs", []):
        product = products[item["product"]]
        case = case_map[int(item["animal_id"])]
        name = item.get("name") or product.name
        category = item.get("category") or product.category
        row = [case.tag_number, name, int(item.get("quantity", 0)), numeric(item["weight"]), item.get("reason", "")]
        if item.get("rejected"):
            rejected.append(row)
        else:
            outputs.append(row)
            totals[category] += numeric(item["weight"])
            if category == "meat":
                meat_by_animal[case.pk] += numeric(item["weight"])
            elif category == "offal":
                offal[name].append((case.tag_number, numeric(item["weight"])))
    # Carcass mass is separate from live mass. Never add the entered cuts to
    # their full carcass mass a second time. Rejected meat is not accepted.
    meat_weight = Decimal(0)
    meat_rows = []
    for case in animals:
        details = document.payload.get("animals", {}).get(str(case.pk), {})
        declared = numeric(details.get("carcass_weight") or case.snapshot.get("carcass_weight"))
        all_meat = [item for item in document.payload.get("outputs", [])
                    if int(item["animal_id"]) == case.pk and (item.get("category") or products[item["product"]].category) == "meat"]
        if all_meat:
            accepted_weight = meat_by_animal[case.pk]
            meat_weight += accepted_weight
            if accepted_weight:
                meat_rows.append((f"Мясо ({case.tag_number})", accepted_weight))
        elif declared is not None and not any(int(item["animal_id"]) == case.pk for item in document.payload.get("outputs", [])):
            meat_weight += declared
            meat_rows.append((f"Мясо ({case.tag_number})", declared))
    _write_slaughter_output_rows(sheet, meat_rows, offal, meat_weight, totals["offal"])
    table_sheet(workbook, "Животные", ["Бирка", "С участка", "Голов", "Масса, кг", "Заключение ветврача"], animal_rows)
    table_sheet(workbook, "Выход продукции", ["Бирка", "Номенклатура", "Количество, шт.", "Масса, кг", "Примечание"], outputs)
    table_sheet(workbook, "Брак — не поступает", ["Бирка", "Номенклатура", "Количество, шт.", "Масса, кг", "Причина брака"], rejected)
    return workbook


def live_workbook(document):
    """Correction worksheet; initial SP-54 always comes from the original exporter.

    This accompanies structured amendments. The user supplies the corrected
    signed act; its uploaded bytes become the next version.
    """
    workbook = Workbook()
    workbook.remove(workbook.active)
    case_map = {case.pk: case for case in document.animals.all()}
    rows = [[case_map[int(line["animal_id"])].tag_number, 1, numeric(line["weight"])] for line in document.payload.get("outputs", [])]
    sheet = table_sheet(workbook, "Данные СП-54", ["Бирка", "Голов", "Живая масса, кг"], rows)
    sheet.cell(len(rows) + 4, 1, "Приложите исправленный СП-54 для утверждения этих данных.")
    return workbook


def invoice_workbook(document):
    from .models import StockLot
    workbook = Workbook()
    workbook.remove(workbook.active)
    rows = []
    for item in document.payload.get("lines", []):
        lot = StockLot.objects.select_related("product", "animal").get(pk=item["lot_id"])
        rows.append([lot.animal.tag_number, item.get("name") or lot.product.name, item["quantity"], numeric(item["weight"]), item.get("order_line_id") or ""])
    sheet = table_sheet(workbook, "Товарная накладная", ["Бирка", "Номенклатура", "Количество, шт.", "Масса, кг", "Строка заявки"], rows)
    text_cell(sheet, len(rows) + 4, 1, f"Тестовый шаблон товарной накладной № {document.number or document.pk} от {document.date:%d.%m.%Y}")
    text_cell(sheet, len(rows) + 5, 1, f"Получатель: {document.payload.get('customer', '')}")
    text_cell(sheet, len(rows) + 6, 1, f"Заявка: {document.order_id or 'не связана'}")
    sheet.merge_cells(start_row=len(rows) + 4, start_column=1, end_row=len(rows) + 4, end_column=5)
    return workbook
