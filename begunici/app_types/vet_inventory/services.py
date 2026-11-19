"""Accounting commands for medicines; treatment integration lives in bridge.py."""
import hashlib
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from begunici.app_types.inventory.documents import read_upload
from begunici.app_types.inventory.models import write_stock_audit_log
from begunici.app_types.inventory.permissions import require_inventory
from begunici.app_types.inventory.validation import amount

from .models import VetAudit, VetDocument, VetMovement, VetOrder, VetProduct, VetSettings, VetVersion
from .permissions import require_document_editor, require_receiving


def number(value):
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result

WRITEOFF_REASONS = [
    ("expired", "Истёк срок годности"), ("spoilage", "Порча / нарушение хранения"),
    ("loss", "Повреждение / утрата"), ("other", "Другая причина"),
]

CATALOG_UNITS = [("ml", "мл"), ("g", "г"), ("pcs", "шт.")]
CATALOG_CONCENTRATIONS = [choice for choice in VetProduct._meta.get_field("concentration_unit").choices
                          if choice[0].startswith("percent_")]


def catalog_name(base_name, unit, details):
    name = base_name
    if details.get("concentration"):
        value = number(details["concentration"]).replace(".", ",")
        kind = details["concentration_unit"]
        suffix = "%" if kind.startswith("percent_") else " " + dict(VetProduct._meta.get_field("concentration_unit").choices)[kind]
        name += " " + value + suffix
    if details.get("package_size"):
        name += " (" + number(details["package_size"]).replace(".", ",") + " " + dict(CATALOG_UNITS).get(
            unit, dict(VetProduct._meta.get_field("unit").choices).get(unit, "")) + ")"
    return text(name, "Полное наименование", 120)


def check_catalog_choices(unit, details, product=None):
    if unit not in dict(CATALOG_UNITS) and (product is None or product.unit != unit):
        raise ValidationError("Основная единица: выберите мл, г или шт.")
    kind = details.get("concentration_unit")
    if kind and kind not in dict(CATALOG_CONCENTRATIONS) and (
            product is None or product.concentration_unit != kind or product.concentration != details["concentration"]):
        raise ValidationError("Выберите один из типов процентной концентрации.")


def writeoff_reason(value):
    if value not in dict(WRITEOFF_REASONS):
        raise ValidationError("Выберите причину списания.")
    return {"reason": value, "reason_label": dict(WRITEOFF_REASONS)[value]}


def product_restrictions(product):
    # JSON snapshots intentionally stay independent of mutable catalog names.
    # Iteration also supports the existing SQLite preview; JSON containment is
    # PostgreSQL-only. Read just the line arrays, never attached binary files.
    used = product.movements.exists()
    if not used:
        for collection in (VetOrder.objects.values_list("lines", flat=True),
                           VetVersion.objects.values_list("payload__lines", flat=True)):
            if any(any(row.get("product") == product.pk for row in (lines or [])) for lines in collection.iterator()):
                used = True
                break
    return {"unit_locked": used or product.norms.exists() or product.vettreatment_set.exists() or product.clinical_doses.exists(), "size_locked": used}


def product_name_exists(name, exclude_pk=None):
    products = VetProduct.objects.all()
    if exclude_pk is not None:
        products = products.exclude(pk=exclude_pk)
    # SQLite's ILIKE/NOCASE does not fold Cyrillic; use the same comparison on
    # both preview and PostgreSQL. Callers hold the catalog/accounting lock.
    return any(existing.casefold() == name.casefold() for existing in products.values_list("name", flat=True))


def product_details(unit, values):
    size = values.get("package_size")
    size = amount(size, "Размер упаковки") if str(size or "").strip() else None
    substance = text(values.get("active_substance"), "Действующее вещество", 120, False)
    concentration, concentration_unit = values.get("concentration"), values.get("concentration_unit") or ""
    if str(concentration or "").strip():
        try:
            concentration = Decimal(str(concentration).replace(",", "."))
        except InvalidOperation:
            raise ValidationError("Концентрация: введите положительное число.")
        if not concentration.is_finite() or concentration <= 0 or concentration > Decimal("999999999.999999") or concentration.as_tuple().exponent < -6:
            raise ValidationError("Концентрация: положительное число, не более 6 знаков после запятой.")
        allowed = {"ml": {"mg/ml", "g/ml", "percent_wv", "percent_vv"},
                   "l": {"mg/ml", "g/ml", "percent_wv", "percent_vv"},
                   "g": {"mg/g", "g/g", "percent_ww"}, "kg": {"mg/g", "g/g", "percent_ww"}}
        if concentration_unit not in allowed.get(unit, set()):
            raise ValidationError("Единица концентрации несовместима с единицей препарата.")
        if concentration_unit.startswith("percent") and concentration > 100:
            raise ValidationError("Процент концентрации не может превышать 100.")
    else:
        concentration, concentration_unit = None, ""
    return dict(package_size=size, active_substance=substance,
                concentration=concentration, concentration_unit=concentration_unit)


@transaction.atomic
def update_product(user, pk, revision, name, category, unit, *, automatic_name=False, **details):
    config = lock(user, allow_receiving=True)
    product = VetProduct.objects.select_for_update().get(pk=pk)
    if str(product.revision) != str(revision):
        raise ValidationError("Номенклатура уже изменена. Обновите страницу перед редактированием.")
    if category not in dict(VetProduct._meta.get_field("category").choices) or unit not in dict(VetProduct._meta.get_field("unit").choices):
        raise ValidationError("Выберите категорию и единицу измерения из списка.")
    name = text(name, "Название", 120)
    automatic_name = automatic_name or bool(product.base_name)
    restrictions = product_restrictions(product)
    if restrictions["unit_locked"] and product.unit != unit:
        raise ValidationError("Единица уже используется в документах или нормах. Для другой единицы создайте отдельную номенклатуру.")
    metadata = product_details(unit, details) if details else {}
    if metadata and "active_substance" not in details:
        metadata["active_substance"] = product.active_substance
    if automatic_name:
        check_catalog_choices(unit, metadata, product)
        naming = {key: metadata.get(key, getattr(product, key)) for key in
                  ("package_size", "concentration", "concentration_unit")}
        if product.base_name and restrictions["size_locked"] and naming["package_size"] != product.package_size:
            raise ValidationError("Для другой фасовки создайте отдельную позицию. Фасовку в используемой карточке менять нельзя.")
        # Legacy names are not parsed or rewritten when unrelated fields are saved.
        unchanged_legacy = not product.base_name and name == product.name and unit == product.unit and all(
            naming[key] == getattr(product, key) for key in naming)
        if not unchanged_legacy:
            metadata["base_name"] = name
            name = catalog_name(name, unit, naming)
    if product_name_exists(name, exclude_pk=pk):
        raise ValidationError("Такая номенклатура уже существует.")
    if product.movements.exists() and (product.concentration or product.base_name) and any(
            metadata.get(key, getattr(product, key)) != getattr(product, key)
            for key in ("concentration", "concentration_unit", "active_substance")):
        raise ValidationError("Для другой концентрации или действующего вещества создайте отдельную позицию. Старый остаток нельзя смешивать с новым.")
    before = {"name": product.name, "category": product.get_category_display(),
              "unit": product.get_unit_display()}
    before.update({key: str(getattr(product, key) or "") for key in metadata})
    product.name, product.category, product.unit = name, category, unit
    for key, value in metadata.items():
        setattr(product, key, value)
    product.revision += 1
    product.save(update_fields=["name", "category", "unit", "revision", *metadata])
    config.revision += 1
    config.save(update_fields=["revision"])
    audit(user, "Изменена номенклатура", product=product.pk, before=before,
          after={"name": product.name, "category": product.get_category_display(),
                 "unit": product.get_unit_display(),
                 **{key: str(value) if value is not None else "" for key, value in metadata.items()}})
    return product


def lock(user, *, allow_receiving=False):
    if allow_receiving:
        require_receiving(user)
    else:
        require_inventory(user)
    return VetSettings.objects.select_for_update().get(pk=1)


@transaction.atomic
def audit(user, action, **data):
    VetAudit.objects.create(created_by=user, action=action, data=data)
    write_stock_audit_log(user, "Склад ветпрепаратов", action, data)


def token(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        raise ValidationError("Обновите страницу перед сохранением.")


def text(value, label, max_length, required=True):
    value = str(value or "").strip()
    if (required and not value) or len(value) > max_length:
        raise ValidationError(f"{label}: заполните поле (до {max_length} символов).")
    return value


def valid_date(value):
    try:
        result = date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError("Укажите дату документа.")
    if result > timezone.localdate():
        raise ValidationError("Приход и фактический расход нельзя оформлять будущей датой.")
    return result


def normalize_lines(rows, allow_empty=False, allow_packages_only=False):
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValidationError("Допускается не более 200 позиций.")
    result, used = [], set()
    products = {p.pk: p for p in VetProduct.objects.all()}
    for row in rows:
        if not isinstance(row, dict):
            raise ValidationError("Некорректная строка номенклатуры.")
        try:
            product = products[int(row["product"])]
        except (KeyError, ValueError, TypeError):
            raise ValidationError("Номенклатура не найдена.")
        quantity = amount(row.get("amount") or 0, "Количество", allow_zero=True)
        packages = amount(row.get("packages") or 0, "Упаковки", allow_zero=True)
        raw_size = row.get("package_size", product.package_size if packages > 0 else None)
        size = amount(raw_size, "Размер упаковки") if str(raw_size or "").strip() else None
        if product.base_name and (quantity or packages) and size is not None and size != product.package_size:
            raise ValidationError(f"{product.name}: для другой фасовки создайте отдельную позицию номенклатуры.")
        if product.base_name and packages and size is None:
            size = product.package_size
        if size and (quantity or packages):
            if packages <= 0 or packages != packages.to_integral_value():
                raise ValidationError(f"{product.name}: укажите целое число упаковок для выбранной фасовки.")
            calculated = amount((size * packages).normalize(), "Общее количество")
            if quantity and quantity != calculated:
                raise ValidationError(f"{product.name}: количество должно равняться числу упаковок × их размеру.")
            quantity = calculated
        if quantity == 0 and packages == 0:
            continue
        key = (product.pk, size)
        if key in used:
            raise ValidationError("Объедините повторяющиеся позиции препарата в одну строку.")
        used.add(key)
        if quantity == 0 and not allow_packages_only:
            raise ValidationError(f"{product.name}: укажите количество в {product.get_unit_display()}.")
        result.append({"product": product.pk, "name": product.name, "unit": product.get_unit_display(),
                       "amount": number(quantity), "packages": number(packages),
                       **({"package_size": number(size)} if size else {})})
    if not result and not allow_empty:
        raise ValidationError("Добавьте хотя бы одну позицию с положительным количеством.")
    return result


def accounting_lines(lines):
    # The retired package label must not make an unchanged historical draft dirty.
    return [{key: value for key, value in line.items() if key != "package"} for line in lines]


def accounting_payload(payload):
    return {**payload, "lines": accounting_lines(payload["lines"])}


def balances():
    return {row["product_id"]: (row["amount"] or Decimal(0), row["packages"] or Decimal(0))
            for row in VetMovement.objects.values("product_id").annotate(amount=Sum("amount"), packages=Sum("packages"))}


def stock_rows():
    from .packaging import grouped_stock, describe
    stock = balances()
    lots = grouped_stock()
    rows = []
    for product in VetProduct.objects.all():
        available, packages = stock.get(product.pk, (Decimal(0), Decimal(0)))
        sizes, unclassified = describe(lots.get(product.pk, []))
        if not lots.get(product.pk):
            unclassified = available
        label = ""
        if product.concentration:
            value = number(product.concentration).replace(".", ",")
            if product.concentration_unit.startswith("percent_"):
                existing = [Decimal(match.replace(",", ".")) for match in
                            re.findall(r"(\d+(?:[.,]\d+)?)\s*%", product.name)]
                label = "" if product.concentration in existing else value + "%"
            else:
                label = value + " " + product.get_concentration_unit_display()
                normalized = re.sub(r"\s+", "", product.name.casefold()).replace(".", ",")
                if re.search(r"(?<![\d,])" + re.escape(re.sub(r"\s+", "", label.casefold())), normalized):
                    label = ""
        measure = physical_measure(product)
        rows.append({"id": product.pk, "name": product.name, "unit": product.get_unit_display(),
                     "group_name": common_product_name(product), "category": product.category,
                     "measure": measure, "measured_available": available * measure[2],
                     "display_name": product.name + (" · " + label if label else ""),
                     "available": available, "packages": packages,
                     "sizes": sizes, "unclassified": unclassified})
    return rows


def common_product_name(product):
    if product.base_name.strip():
        return product.base_name.strip()
    name = product.name.strip()
    # Strip only suffixes confirmed by structured metadata, never infer a strength.
    if product.package_size:
        match = re.search(r"\s*\((\d+(?:[.,]\d+)?)\s*(мл|г|шт\.?|л|кг)\)\s*$", name, re.I)
        if match and Decimal(match[1].replace(",", ".")) == product.package_size and match[2].casefold().rstrip(".") == product.get_unit_display().rstrip("."):
            name = name[:match.start()].strip()
    if product.concentration and product.concentration_unit.startswith("percent_"):
        match = re.search(r"\s*(\d+(?:[.,]\d+)?)\s*%\s*$", name)
        if match and Decimal(match[1].replace(",", ".")) == product.concentration:
            name = name[:match.start()].strip()
    return name or product.name


def physical_measure(product):
    unit = {"l": "ml", "kg": "g"}.get(product.unit, product.unit)
    return "product", unit, Decimal(1000) if product.unit in {"l", "kg"} else Decimal(1)


def product_groups(products=None):
    stock, groups = balances(), {}
    for product in products if products is not None else VetProduct.objects.all():
        name = common_product_name(product)
        group = groups.setdefault((name.casefold(), product.category),
            {"id": str(product.pk), "name": name, "label": name, "variants": []})
        group["variants"].append({"id": str(product.pk), "name": product.name,
            "unit": product.get_unit_display(), "available": number(stock.get(product.pk, (Decimal(0), Decimal(0)))[0])})
    return list(groups.values())


def expense_measure(product):
    from .rules import convert_dose
    if product.concentration:
        for unit in ("g", "ml"):
            try:
                convert_dose(product, Decimal(1), "active", unit)
                strengths = {"mg/ml": product.concentration / 1000, "g/ml": product.concentration,
                    "mg/g": product.concentration / 1000, "g/g": product.concentration,
                    "percent_wv": product.concentration / 100, "percent_ww": product.concentration / 100,
                    "percent_vv": product.concentration / 100}
                factor = strengths[product.concentration_unit] * (1000 if product.unit in {"l", "kg"} else 1)
                return "active", unit, factor
            except ValidationError:
                continue
        raise ValidationError(f"{product.name}: проверьте концентрацию и её единицу в карточке препарата.")
    unit = {"l": "ml", "kg": "g"}.get(product.unit, product.unit)
    return "product", unit, Decimal(1000) if product.unit in {"l", "kg"} else Decimal(1)


def expense_group_key(product):
    return (common_product_name(product).casefold(), product.category, *expense_measure(product)[:2])


def expense_groups(products=None):
    from .rules import DOSE_UNITS
    stock = balances()
    groups = {}
    for product in products if products is not None else VetProduct.objects.all():
        basis, unit, factor = expense_measure(product)
        name = common_product_name(product)
        key = expense_group_key(product)
        group = groups.setdefault(key, {"id": str(product.pk), "name": name, "basis": basis,
            "unit": unit, "unit_label": dict(DOSE_UNITS)[unit], "available": Decimal(0), "variants": []})
        available = stock.get(product.pk, (Decimal(0), Decimal(0)))[0]
        group["available"] += available * factor
        group["variants"].append({"id": str(product.pk), "name": product.name,
            "available": number(available), "unit": product.get_unit_display()})
    result = list(groups.values())
    for group in result:
        label = "действующее вещество" if group["basis"] == "active" else "без концентрации"
        group["label"] = f"{group['name']} · {label}, {group['unit_label']}"
        group["available"] = number(group["available"])
    return result


def group_stock_rows(rows):
    from .rules import DOSE_UNITS
    groups = {}
    for row in rows:
        group = groups.setdefault((row["group_name"].casefold(), row["category"]),
            {"name": row["group_name"], "rows": [], "totals": {}})
        group["rows"].append(row)
        basis, unit, _factor = row["measure"]
        total = group["totals"].setdefault((basis, unit), {"basis": basis,
            "unit": dict(DOSE_UNITS)[unit], "amount": Decimal(0)})
        total["amount"] += row["measured_available"]
        row["measured_unit"] = dict(DOSE_UNITS)[unit]
    for group in groups.values():
        group["totals"] = list(group["totals"].values())
    return list(groups.values())


def resolve_group_expenses(requests, *, decimal_places=9):
    from . import packaging
    from .models import VetStockLot
    from .rules import DOSE_UNITS
    if not isinstance(requests, list) or not 1 <= len(requests) <= 200:
        raise ValidationError("Добавьте от 1 до 200 строк расхода.")
    products = {str(p.pk): p for p in VetProduct.objects.all()}
    stock = balances()
    lots = list(VetStockLot.objects.filter(remaining__gt=0).select_related("receipt__document"))
    by_product = defaultdict(list)
    for lot in packaging.order_lots(lots):
        by_product[str(lot.product_id)].append({"lot": lot, "remaining": lot.remaining})
    for pk, product in products.items():
        quantity = stock.get(product.pk, (Decimal(0), Decimal(0)))[0]
        if not by_product[pk] and quantity:
            by_product[pk].append({"lot": None, "remaining": quantity})
    canonical, totals, validated = [], defaultdict(Decimal), set()
    for request in requests:
        if not isinstance(request, dict):
            raise ValidationError("Проверьте строки расхода.")
        try:
            value = Decimal(str(request.get("amount") or 0).strip().replace(",", "."))
        except InvalidOperation:
            raise ValidationError("Количество: введите положительное число.")
        if not value.is_finite() or value < 0 or value > Decimal("999999999.999999999") or value.as_tuple().exponent < -decimal_places:
            raise ValidationError(f"Количество: неотрицательное число, не более {decimal_places} знаков после запятой.")
        if not value:
            continue
        reference = products.get(str(request.get("group")))
        if reference is None:
            raise ValidationError("Выберите общее название препарата.")
        basis, unit, _factor = expense_measure(reference)
        name = common_product_name(reference)
        candidates = [p for p in products.values() if expense_group_key(p) == expense_group_key(reference)]
        variant = str(request.get("variant") or "")
        if variant:
            candidates = [p for p in candidates if str(p.pk) == variant]
            if not candidates:
                raise ValidationError("Выбранный вариант не относится к этой группе и единице измерения.")
        chunks = []
        for product in candidates:
            if product.pk not in validated:
                if sum((part["remaining"] for part in by_product[str(product.pk)]), Decimal(0)) != stock.get(product.pk, (Decimal(0), Decimal(0)))[0]:
                    raise ValidationError(f"{product.name}: остатки фасовок требуют сверки.")
                validated.add(product.pk)
            for part in by_product[str(product.pk)]:
                lot = part["lot"]
                opened = part["remaining"] % lot.capacity if lot and lot.capacity else Decimal(0)
                if opened:
                    chunks.append((0, packaging.lot_order(lot), product, part, opened))
                sealed = part["remaining"] - opened
                if sealed:
                    chunks.append((1, packaging.lot_order(lot), product, part, sealed))
        needed = value
        for _priority, _order, product, part, capacity in sorted(chunks, key=lambda c: (c[0], c[1])):
            if needed <= 0:
                break
            factor = expense_measure(product)[2]
            quantity = min(capacity, (needed / factor).quantize(Decimal("0.001"), rounding=ROUND_CEILING))
            if not quantity:
                continue
            part["remaining"] -= quantity
            totals[product.pk] += quantity
            needed -= quantity * factor
        if needed > 0:
            raise ValidationError(f"{name}: недостаточно остатка в выбранных вариантах препарата.")
        canonical.append({"group": str(reference.pk), "variant": variant, "amount": number(value),
                          "basis": basis, "unit": unit, "unit_label": dict(DOSE_UNITS)[unit], "name": name})
    if not canonical:
        raise ValidationError("Добавьте хотя бы одну позицию с положительным количеством.")
    lines = normalize_lines([{"product": pk, "amount": number(qty), "packages": "0", "package_size": ""}
                             for pk, qty in sorted(totals.items())])
    return lines, canonical


def order_progress(order):
    received = {}
    for document in order.vetdocument_set.filter(kind="receipt", state="posted").prefetch_related("versions"):
        for line in document.versions.first().payload["lines"]:
            key = (line["product"], line.get("package_size", ""))
            totals = received.setdefault(key, {"amount": Decimal(0), "packages": Decimal(0)})
            totals["amount"] += Decimal(line["amount"])
            totals["packages"] += Decimal(line["packages"])
    rows, any_received, complete = [], False, True
    for line in order.lines:
        if line.get("package_size"):
            totals = received.get((line["product"], line["package_size"]), {})
        else:
            totals = {field: sum((value[field] for (pk, _), value in received.items() if pk == line["product"]), Decimal(0))
                      for field in ("amount", "packages")}
        delivered = totals.get("amount", Decimal(0))
        packs = totals.get("packages", Decimal(0))
        missing = max(Decimal(line["amount"]) - delivered, Decimal(0))
        missing_packs = max(Decimal(line["packages"]) - packs, Decimal(0))
        covered = missing == 0 and missing_packs == 0
        complete = complete and covered
        any_received = any_received or delivered > 0 or packs > 0
        rows.append({**line, "received": delivered, "received_packages": packs,
                     "missing": missing, "missing_packages": missing_packs, "covered": covered})
    return {"rows": rows, "complete": complete, "partial": any_received and not complete,
            "label": "Выполнена" if complete else "Частично выполнена" if any_received else "Ожидает прихода"}


@transaction.atomic
def create_product(user, name, category, unit, *, automatic_name=False, **details):
    lock(user, allow_receiving=True)
    if category not in dict(VetProduct._meta.get_field("category").choices) or unit not in dict(VetProduct._meta.get_field("unit").choices):
        raise ValidationError("Выберите категорию и единицу измерения из списка.")
    name = text(name, "Название", 120)
    metadata = product_details(unit, details)
    if automatic_name:
        check_catalog_choices(unit, metadata)
        metadata["base_name"] = name
        name = catalog_name(name, unit, metadata)
    if product_name_exists(name):
        raise ValidationError("Такая номенклатура уже существует.")
    product = VetProduct.objects.create(name=name, category=category, unit=unit,
                                       **metadata)
    config = VetSettings.objects.get(pk=1)
    config.revision += 1
    config.save(update_fields=["revision"])
    audit(user, "Добавлена номенклатура", product=product.pk, name=product.name, unit=unit)
    return product


@transaction.atomic
def create_order(user, supplier, note, lines, request_token):
    lock(user, allow_receiving=True)
    request_token = token(request_token)
    existing = VetOrder.objects.filter(token=request_token).first()
    if existing:
        return existing
    order = VetOrder.objects.create(created_by=user, supplier=text(supplier, "Поставщик", 200),
                                     note=text(note, "Примечание", 4000, False),
                                     lines=normalize_lines(lines), token=request_token)
    audit(user, "Создана заявка на приход", order=order.pk)
    return order


def add_version(document, user, payload, upload=None, previous=None):
    data = {"filename": "", "content": b"", "content_type": "", "sha256": ""}
    if previous:
        data = {key: getattr(previous, key) for key in data}
    if upload:
        content, filename, content_type = read_upload(upload)
        data = {"filename": filename, "content": content, "content_type": content_type,
                "sha256": hashlib.sha256(content).hexdigest()}
    return VetVersion.objects.create(document=document, number=document.revision,
                                      created_by=user, payload=payload, **data)


@transaction.atomic
def create_document(user, kind, document_date, number_, lines, note, request_token, order_id=None, upload=None, reason=None, group_expenses=None):
    lock(user, allow_receiving=kind == "receipt")
    if kind not in {"receipt", "consume", "writeoff"}:
        raise ValidationError("Неизвестный вид документа.")
    request_token = token(request_token)
    existing = VetDocument.objects.filter(token=request_token).first()
    if existing:
        require_document_editor(user, existing.kind)
        return existing
    order = None
    if kind == "receipt":
        order = VetOrder.objects.filter(pk=order_id).first()
        if not order:
            raise ValidationError("Приходная накладная создаётся из входящей заявки.")
    if group_expenses is not None:
        if kind not in {"consume", "writeoff"}:
            raise ValidationError("Групповой выбор доступен только для расхода и списания.")
        clean_lines, group_expenses = resolve_group_expenses(group_expenses)
    else:
        clean_lines = normalize_lines(lines, allow_packages_only=kind in {"consume", "writeoff"})
    if order and any(line["product"] not in {r["product"] for r in order.lines} for line in clean_lines):
        raise ValidationError("В накладной есть препарат, не указанный в заявке. Создайте для него заявку.")
    document = VetDocument.objects.create(kind=kind, date=valid_date(document_date), order=order,
        number=text(number_, "Номер накладной", 100, kind == "receipt"), token=request_token, created_by=user)
    payload = {"lines": clean_lines, "note": text(note, "Примечание", 4000, False)}
    if group_expenses is not None:
        payload["group_expenses"] = group_expenses
    if kind == "writeoff":
        document.number = document.act_number
        document.save(update_fields=["number"])
        payload.update(writeoff_reason(reason))
        payload["note"] = text(note, "Обоснование списания", 4000)
    if kind == "consume":
        payload["note"] = text(note, "Основание прочего расхода", 4000)
    add_version(document, user, payload, upload)
    audit(user, "Создан черновик", document=document.pk)
    return document


def checked_document(user, pk, revision):
    lock(user, allow_receiving=True)
    document = VetDocument.objects.select_for_update().get(pk=pk)
    require_document_editor(user, document.kind)
    if hasattr(document, "clinical_episode"):
        raise ValidationError("Итоговый расход лечения подтверждается в истории болезни.")
    if str(document.revision) != str(revision):
        raise ValidationError("Документ изменился. Обновите страницу и проверьте новую версию.")
    return document


@transaction.atomic
def edit_draft(user, pk, revision, lines, note, upload=None, replace_confirmed=False, reason=None, group_expenses=None):
    document = checked_document(user, pk, revision)
    if document.state != "draft":
        raise ValidationError("Изменять можно только черновик. Для подтверждённого документа используйте сторно.")
    previous = document.versions.first()
    if upload and previous.filename and not replace_confirmed:
        raise ValidationError("Подтвердите замену вложения. Предыдущая версия останется в истории.")
    if group_expenses is not None:
        if document.kind not in {"consume", "writeoff"}:
            raise ValidationError("Групповой выбор доступен только для расхода и списания.")
        clean_lines, group_expenses = resolve_group_expenses(group_expenses)
    else:
        clean_lines = normalize_lines(lines, allow_packages_only=document.kind in {"consume", "writeoff"})
    if document.order_id and any(line["product"] not in {r["product"] for r in document.order.lines} for line in clean_lines):
        raise ValidationError("Позиция отсутствует в заявке.")
    payload = {**previous.payload, "lines": clean_lines, "note": text(note, "Примечание", 4000, False)}
    payload.pop("group_expenses", None)
    if group_expenses is not None:
        payload["group_expenses"] = group_expenses
    if document.kind == "consume":
        payload["note"] = text(note, "Основание прочего расхода", 4000)
    if document.kind == "writeoff":
        payload.update(writeoff_reason(reason if reason is not None else previous.payload.get("reason")))
        payload["note"] = text(note, "Обоснование списания", 4000)
        if previous.filename and not upload and accounting_payload(payload) != accounting_payload(previous.payload):
            raise ValidationError("Состав или причина списания изменились. Приложите исправленный акт; старый останется в истории.")
    document.revision += 1
    document.save(update_fields=["revision"])
    add_version(document, user, payload, upload, previous)
    audit(user, "Исправлен черновик", document=document.pk, revision=document.revision)
    return document


@transaction.atomic
def confirm_document(user, pk, revision):
    document = checked_document(user, pk, revision)
    if document.state == "posted":
        return document  # A repeated confirmation never doubles the ledger.
    if document.state != "draft":
        raise ValidationError("Этот документ уже отменён или сторнирован.")
    version = document.versions.first()
    if "group_expenses" in version.payload:
        lines, requests = resolve_group_expenses(version.payload["group_expenses"])
        if lines != accounting_lines(version.payload["lines"]) or requests != version.payload["group_expenses"]:
            raise ValidationError("Остатки или варианты препарата изменились. Обновите состав черновика и проверьте расшифровку перед подтверждением.")
    if document.kind == "writeoff":
        writeoff_reason(version.payload.get("reason"))
        text(version.payload.get("note"), "Обоснование списания", 4000)
        if not version.filename or not version.content:
            raise ValidationError("Для списания прикрепите подтверждающий акт (PDF или XLSX).")
    sign = 1 if document.kind == "receipt" else -1
    apply_movements(document, version.payload["lines"], sign)
    document.state, document.posted_at, document.posted_by = "posted", timezone.now(), user
    document.save(update_fields=["state", "posted_at", "posted_by"])
    action = {"receipt": "Подтверждён приход", "consume": "Подтверждён расход", "writeoff": "Подтверждено списание по акту"}[document.kind]
    audit(user, action, document=document.pk, revision=document.revision)
    return document


@transaction.atomic
def apply_movements(document, lines, sign):
    from . import packaging
    VetSettings.objects.select_for_update().get(pk=1)
    current = balances()
    grouped = defaultdict(list)
    for line in lines:
        grouped[line["product"]].append(line)
    for pk, rows in grouped.items():
        product = VetProduct.objects.get(pk=pk)
        if any(line["unit"] != product.get_unit_display() for line in rows):
            raise ValidationError(f"{product.name}: единица документа отличается от текущей. Требуется сверка.")
        quantity = sum((Decimal(line["amount"]) for line in rows), Decimal(0)) * sign
        packages = sum((Decimal(line["packages"]) for line in rows), Decimal(0)) * sign
        old_quantity, old_packages = current.get(pk, (Decimal(0), Decimal(0)))
        if old_quantity + quantity < 0 or old_packages + packages < 0:
            raise ValidationError(f"{product.name}: недостаточно остатков. Доступно {number(old_quantity)} {product.get_unit_display()}, упаковок {number(old_packages)}.")
        lots = packaging.ensure_lots(product, old_quantity, old_packages)
        original = VetMovement.objects.filter(document_id=document.reversal_of_id, product_id=pk).first() if document.reversal_of_id else None
        if original and original.allocations:
            allocations = packaging.reverse_allocations(original, product, sign)
            packages = sum((Decimal(a["packages"]) for a in allocations), Decimal(0)) * sign
        elif sign > 0:
            allocations = packaging.receive(product, rows)
        else:
            allocations = packaging.consume(lots, rows)
            packages = -sum((Decimal(a["packages"]) for a in allocations), Decimal(0))
        movement = VetMovement.objects.create(document=document, product=product, amount=quantity,
                                             packages=packages, allocations=allocations)
        if sign > 0 and not original:
            from .models import VetStockLot
            VetStockLot.objects.filter(pk__in=[a["lot"] for a in allocations]).update(receipt=movement)


@transaction.atomic
def cancel_draft(user, pk, revision):
    document = checked_document(user, pk, revision)
    if document.state != "draft":
        raise ValidationError("Отменить можно только черновик.")
    document.state = "cancelled"
    document.save(update_fields=["state"])
    audit(user, "Отменён черновик", document=document.pk)


@transaction.atomic
def reverse_document(user, pk, reason):
    lock(user)
    document = VetDocument.objects.select_for_update().get(pk=pk)
    if hasattr(document, "clinical_episode"):
        raise ValidationError("Расход завершённого лечения сохраняется в истории болезни.")
    reason = text(reason, "Причина сторно", 2000)
    if document.state != "posted" or document.kind in {"reversal", "treatment"}:
        raise ValidationError("Сторно доступно для подтверждённого прихода или расхода.")
    reversal = VetDocument.objects.create(kind="reversal", order=document.order, reversal_of=document,
                                           created_by=user, posted_by=user, posted_at=timezone.now(), state="posted")
    lines = accounting_lines(document.versions.first().payload["lines"])
    add_version(reversal, user, {"lines": lines, "note": reason})
    apply_movements(reversal, lines, -1 if document.kind == "receipt" else 1)
    document.state = "reversed"
    document.save(update_fields=["state"])
    audit(user, "Сторно", document=document.pk, reversal=reversal.pk, reason=reason)
    return reversal
