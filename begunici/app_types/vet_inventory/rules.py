"""User-entered accounting estimates; these rules never prescribe treatment."""
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta

from django.core.exceptions import ValidationError
from django.db import transaction

from begunici.app_types.veterinary.vet_models import VeterinaryCare
from begunici.app_types.inventory.validation import amount
from .models import VetNorm, VetProduct, VetSettings
from .permissions import require_treat
from .services import audit, number, common_product_name, expense_group_key, expense_groups, expense_measure

DOSE_UNITS = [("ml", "мл"), ("l", "л"), ("mg", "мг"), ("g", "г"), ("kg", "кг"),
              ("mcg", "мкг"), ("pcs", "шт."), ("dose", "доз")]
WEIGHT_REQUIRED_MESSAGE = "Укажите вес вручную для расчёта расхода. Запись взвешивания не создаётся."
UNIT_FACTORS = {"ml": ("volume", Decimal(1)), "l": ("volume", Decimal(1000)),
    "mg": ("mass", Decimal(1)), "g": ("mass", Decimal(1000)), "kg": ("mass", Decimal(1000000)),
    "mcg": ("mass", Decimal("0.001")), "pcs": ("count", Decimal(1)), "dose": ("dose", Decimal(1))}


def convert_dose(product, value, basis, unit):
    source_dimension, source_factor = UNIT_FACTORS[unit]
    target_dimension, target_factor = UNIT_FACTORS[product.unit]
    if basis == "product":
        if source_dimension != target_dimension:
            raise ValidationError("Единица нормы несовместима с единицей препарата.")
        return value * source_factor / target_factor
    if not product.concentration:
        raise ValidationError("В карточке препарата укажите концентрацию.")
    concentration = product.concentration
    kind = product.concentration_unit
    dimensions = {"mg/ml": ("mass", "volume", concentration), "g/ml": ("mass", "volume", concentration * 1000),
        "mg/g": ("mass", "mass", concentration), "g/g": ("mass", "mass", concentration * 1000),
        "percent_wv": ("mass", "volume", concentration * 10),
        "percent_ww": ("mass", "mass", concentration * 10),
        "percent_vv": ("volume", "volume", concentration / 100)}
    if kind not in dimensions:
        raise ValidationError("Выберите единицу концентрации в карточке препарата.")
    active_dimension, content_dimension, strength = dimensions[kind]
    if source_dimension != active_dimension or target_dimension != content_dimension:
        raise ValidationError("Единицы нормы, концентрации и препарата несовместимы.")
    # Concentrations with a mass denominator use grams; mass units above use mg.
    content_factor = Decimal(1000) if content_dimension == "mass" else Decimal(1)
    return value * source_factor / strength * content_factor / target_factor


def dose_unit_choices(product, basis, existing=None):
    if product is None:
        return []
    if basis == "product":
        choices = [(product.unit, dict(DOSE_UNITS)[product.unit])]
    elif basis == "active":
        choices = []
        for unit, label in DOSE_UNITS:
            try:
                convert_dose(product, Decimal(1), basis, unit)
            except ValidationError:
                continue
            choices.append((unit, label))
    else:
        return []
    # Retain old compatible units without relabelling their numeric rates.
    if existing and existing.product_id == product.pk and existing.dose_basis == basis:
        unit = existing.dose_unit or product.unit
        if unit not in dict(choices) and unit in dict(DOSE_UNITS):
            try:
                convert_dose(product, Decimal(1), basis, unit)
            except ValidationError:
                pass
            else:
                choices.append((unit, dict(DOSE_UNITS)[unit] + " (сохранённая единица)"))
    return choices


def automatic_units(product):
    basis, unit, _factor = expense_measure(product)
    if basis == "active":
        return dose_unit_choices(product, basis)
    if product.category in {"material", "other"}:
        return [(unit, dict(DOSE_UNITS)[unit])]
    return []


def norm_groups(products):
    by_id = {str(product.pk): product for product in products}
    groups = expense_groups(products)
    for group in groups:
        group["auto_units"] = automatic_units(by_id[group["id"]])
    return groups


def clean_conditions(rows):
    if not isinstance(rows, list) or len(rows) > 50:
        raise ValidationError("Допускается не более 50 условий нормы.")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValidationError("Проверьте условия нормы.")
        clean = {}
        for prefix, label in (("age", "Возраст, мес."), ("weight", "Вес, кг")):
            start = amount(row.get(prefix + "_from") or 0, label, allow_zero=True)
            end = amount(row[prefix + "_to"], label) if str(row.get(prefix + "_to") or "").strip() else None
            if end is not None and end <= start:
                raise ValidationError("Верхняя граница должна быть больше нижней; она не включается.")
            if prefix == "age" and any(value is not None and (value != value.to_integral_value() or value > 1200) for value in (start, end)):
                raise ValidationError("Возраст задаётся целыми месяцами от 0 до 1200.")
            clean[prefix + "_from"], clean[prefix + "_to"] = number(start), number(end) if end is not None else ""
        clean["rate"] = number(amount(row.get("rate"), "Норма", allow_zero=True))
        for other in result:
            overlaps = all(
                (not clean[p + "_to"] or Decimal(other[p + "_from"]) < Decimal(clean[p + "_to"]))
                and (not other[p + "_to"] or Decimal(clean[p + "_from"]) < Decimal(other[p + "_to"]))
                for p in ("age", "weight"))
            if overlaps:
                raise ValidationError("Условия пересекаются по возрасту и весу. Животному должна соответствовать только одна норма.")
        result.append(clean)
    return result


def is_shearing(care):
    return bool(care and any(str(getattr(care, field) or "").strip().casefold() == "стрижка"
                             for field in ("care_type", "care_name")))


def clean_bands(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 20:
        raise ValidationError("Задайте от 1 до 20 диапазонов веса.")
    result = []
    previous_end = Decimal(0)
    for index, row in enumerate(rows):
        start = amount(row.get("from"), "Вес от", allow_zero=True)
        end = amount(row.get("to"), "Вес до") if str(row.get("to", "")).strip() else None
        rate = amount(row.get("amount"), "Расход", allow_zero=True)
        if (index and previous_end is None) or start < previous_end or (end is not None and end <= start):
            raise ValidationError("Диапазоны должны идти по возрастанию и не пересекаться. Верхняя граница не включается.")
        result.append({"from": number(start), "to": number(end) if end is not None else "", "amount": number(rate)})
        previous_end = end
    return result


@transaction.atomic
def save_rule(user, care_id, revision, product_id, mode, rate, bands, *,
              dose_basis="product", dose_unit="", weight_step=None, conditions=None,
              group_id=None, variant_id=None, separate=False):
    require_treat(user)
    VetSettings.objects.select_for_update().get(pk=1)
    care = VeterinaryCare.objects.get(pk=care_id)
    if is_shearing(care):
        raise ValidationError("Стрижка не требует расхода ветпрепаратов. Норма не нужна.")
    candidates = VetNorm.objects.filter(care=care)
    rule = candidates.filter(product_id=product_id).first() if separate else candidates.first()
    if str(rule.revision if rule else 0) != str(revision):
        raise ValidationError("Норма уже изменена. Обновите страницу.")
    auto_variant = group_id is not None and not str(variant_id or "").strip()
    if group_id is not None:
        try:
            reference = VetProduct.objects.get(pk=group_id)
            product = VetProduct.objects.get(pk=variant_id) if not auto_variant else reference
        except (VetProduct.DoesNotExist, ValueError, TypeError):
            raise ValidationError("Выберите общее название и вариант препарата.")
        if expense_group_key(product) != expense_group_key(reference):
            raise ValidationError("Выбранный вариант не относится к этой группе и единице измерения.")
        product_id = product.pk
    try:
        product = VetProduct.objects.filter(pk=product_id).first()
    except (ValueError, TypeError):
        product = None
    if not product or mode not in dict(VetNorm._meta.get_field("mode").choices):
        raise ValidationError("Выберите препарат и способ расчёта.")
    auto_units = automatic_units(product) if auto_variant else []
    if auto_variant:
        if not auto_units:
            raise ValidationError("Для автоматического выбора препарата укажите концентрацию в карточке или выберите конкретный вариант.")
        if dose_basis != expense_measure(product)[0]:
            raise ValidationError("При автоматическом выборе норма задаётся по действующему веществу; для материалов без концентрации — по материалу.")
    dose_unit = dose_unit or ((rule.dose_unit or product.unit) if rule and rule.product_id == product.pk
                              and rule.dose_basis == dose_basis else product.unit)
    if dose_basis not in {"product", "active"} or dose_unit not in dict(DOSE_UNITS):
        raise ValidationError("Выберите основу и единицу нормы.")
    convert_dose(product, Decimal(1), dose_basis, dose_unit)
    if dose_unit not in dict(auto_units if auto_variant else dose_unit_choices(product, dose_basis, rule)):
        raise ValidationError("По препарату норма задаётся в его основной единице. Выберите совместимую единицу нормы.")
    clean_conditions_ = clean_conditions(conditions or [])
    step = amount(weight_step, "Шаг веса, кг") if mode == "step" else None
    clean_rate = None if mode == "bands" or clean_conditions_ else amount(rate, "Норма", allow_zero=True)
    clean_rows = clean_bands(bands) if mode == "bands" and not clean_conditions_ else []
    before = rule_data(rule) if rule else None
    if rule is None:
        rule = VetNorm(care=care, revision=0)
    rule.product, rule.mode, rule.rate, rule.bands = product, mode, clean_rate, clean_rows
    rule.auto_variant = auto_variant
    rule.dose_basis, rule.dose_unit = dose_basis, dose_unit
    rule.weight_step, rule.conditions = step, clean_conditions_
    rule.revision += 1
    rule.save()
    audit(user, "Изменена норма обработки", care=care.pk, before=before, after=rule_data(rule))
    return rule


def rule_data(rule):
    group_name = common_product_name(rule.product)
    return {"product": rule.product_id, "name": group_name if rule.auto_variant else rule.product.name,
            "group_name": group_name, "auto_variant": rule.auto_variant, "unit": rule.product.get_unit_display(),
            "mode": rule.mode, "mode_label": rule.get_mode_display(),
            "rate": number(rule.rate) if rule.rate is not None else "", "bands": rule.bands, "revision": rule.revision,
            "dose_basis": rule.dose_basis, "dose_basis_label": rule.get_dose_basis_display(),
            "dose_unit": rule.dose_unit or rule.product.unit, "dose_unit_label": dict(DOSE_UNITS)[rule.dose_unit or rule.product.unit],
            "weight_step": number(rule.weight_step) if rule.weight_step else "", "conditions": rule.conditions,
            "active_substance": rule.product.active_substance,
            "concentration": number(rule.product.concentration) if rule.product.concentration else "",
            "concentration_unit": rule.product.concentration_unit}


def direct_rule(rule):
    return rule is not None and not rule.auto_variant and rule.dose_basis == "product"


def requires_weight(rule):
    return rule.mode != "head" or any(
        Decimal(condition["weight_from"]) > 0 or condition["weight_to"] for condition in rule.conditions)


@transaction.atomic
def save_product_rules(user, care_id, group_id, rows, conditions):
    require_treat(user)
    VetSettings.objects.select_for_update().get(pk=1)
    from .services import product_groups
    groups = product_groups()
    group = next((group for group in groups if group["id"] == str(group_id)), None)
    if group is None or not isinstance(rows, list) or not isinstance(conditions, list) or len(conditions) > 200:
        raise ValidationError("Выберите общее название и проверьте строки норм.")
    ids = {variant["id"] for variant in group["variants"]}
    if len(rows) != len(ids) or {str(row.get("product")) for row in rows} != ids:
        raise ValidationError("Состав препаратов изменился. Обновите страницу перед сохранением.")
    existing = {str(rule.product_id): rule for rule in VetNorm.objects.filter(care_id=care_id)}
    by_product = {pk: [] for pk in ids}
    for condition in conditions:
        pk = str(condition.get("product"))
        if pk not in ids:
            raise ValidationError("В условиях выберите препарат из текущего списка.")
        by_product[pk].append({key: value for key, value in condition.items() if key != "product"})
    for row in rows:
        rule = existing.get(str(row["product"]))
        if str(rule.revision if rule else 0) != str(row.get("revision")):
            raise ValidationError("Нормы уже изменены. Обновите страницу.")
    for row in rows:
        pk = str(row["product"])
        rule = existing.get(pk)
        if not str(row.get("rate") or "").strip() and not by_product[pk]:
            if rule:
                audit(user, "Удалена норма обработки", care=care_id, before=rule_data(rule))
                rule.delete()
            continue
        save_rule(user, care_id, row["revision"], pk, row["mode"], row.get("rate"), [],
            dose_unit=row.get("unit", ""), weight_step=row.get("weight_step"),
            conditions=by_product[pk], separate=True)


def estimate_product(veterinary, product_id=None, weight=None):
    candidates = VetNorm.objects.select_related("product").filter(care_id=veterinary.veterinary_care_id)
    if product_id in (None, ""):
        available = list(candidates.filter(auto_variant=False, dose_basis="product"))
        if not available and not candidates.exists():
            raise ValidationError("Для этой обработки ещё не задан препарат и норма расхода.")
        if len(available) != 1:
            raise ValidationError("Выберите конкретный препарат для расчёта расхода.")
        rule = available[0]
    else:
        try:
            rule = candidates.filter(product_id=product_id).first()
        except (TypeError, ValueError):
            rule = None
    if not direct_rule(rule):
        raise ValidationError("Для выбранного препарата норма не задана. Укажите расход вручную или настройте норму.")
    return estimate(veterinary, weight=weight, product_id=rule.product_id)


def estimate(veterinary, weight=None, product_id=None):
    if is_shearing(veterinary.veterinary_care):
        raise ValidationError("Стрижка не требует расхода ветпрепаратов.")
    candidates = VetNorm.objects.select_related("product").filter(care_id=veterinary.veterinary_care_id)
    rule = candidates.filter(product_id=product_id).first() if product_id is not None else candidates.first()
    if rule is None:
        raise ValidationError("Для этой обработки ещё не задан препарат и норма расхода.")
    calculation = rule_data(rule)
    needs_weight = bool(requires_weight(rule))
    calculation["requires_weight"] = needs_weight
    measured = amount(weight, "Вес для расхода, кг") if str(weight or "").strip() else None
    if needs_weight and measured is None:
        raise ValidationError(WEIGHT_REQUIRED_MESSAGE, code="weight_required")
    if measured is not None:
        calculation.update(weight=number(measured), weight_source="manual")
    rate = rule.rate
    if rule.conditions:
        age_required = any(Decimal(c["age_from"]) > 0 or c["age_to"] for c in rule.conditions)
        months = None
        if age_required:
            from begunici.app_types.animals.models import Ewe, Maker, Ram, Sheep
            born = next((value for model in (Ewe, Maker, Ram, Sheep)
                if (value := model.objects.filter(tag_id=veterinary.tag_id).values_list("birth_date", flat=True).first())), None)
            if not born or born > veterinary.get_care_date():
                raise ValidationError("Для возрастной нормы нужна корректная дата рождения животного.")
            age = relativedelta(veterinary.get_care_date(), born)
            months = age.years * 12 + age.months
            calculation["age_months"] = months
        matches = [c for c in rule.conditions if
            (months is None or Decimal(c["age_from"]) <= months and (not c["age_to"] or months < Decimal(c["age_to"])))
            and (measured is None or Decimal(c["weight_from"]) <= measured and (not c["weight_to"] or measured < Decimal(c["weight_to"])))]
        if len(matches) != 1:
            raise ValidationError("Возраст или вес не попали в условия нормы. Уточните данные или фактический расход.")
        rate = Decimal(matches[0]["rate"])
        calculation["matched_condition"] = matches[0]
    elif rule.mode == "bands":
        band = next((b for b in rule.bands if Decimal(b["from"]) <= measured
                     and (not b["to"] or measured < Decimal(b["to"]))), None)
        if band is None:
            raise ValidationError("Вес животного не попал в заданные диапазоны.")
        rate = Decimal(band["amount"])
    result = rate
    if rule.mode == "weight":
        result *= measured
    elif rule.mode == "step":
        steps = (measured / rule.weight_step).to_integral_value(rounding=ROUND_CEILING)
        calculation["steps"] = number(steps)
        result *= steps
    calculation["dose_amount"] = number(result)
    if rule.auto_variant:
        units = automatic_units(rule.product)
        basis, unit, _factor = expense_measure(rule.product)
        dose_unit = rule.dose_unit or rule.product.unit
        if rule.dose_basis != basis or dose_unit not in dict(units):
            raise ValidationError("Проверьте основу и единицу автоматической нормы после изменения карточки препарата.")
        result *= UNIT_FACTORS[dose_unit][1] / UNIT_FACTORS[unit][1]
        calculation["group_expenses"] = [{"group": str(rule.product_id), "variant": "", "amount": number(result),
            "basis": basis, "unit": unit, "unit_label": dict(DOSE_UNITS)[unit], "name": common_product_name(rule.product)}]
        return rule.product, None, calculation
    result = convert_dose(rule.product, result, rule.dose_basis, rule.dose_unit or rule.product.unit)
    result = result.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    if result == 0 and rate > 0:
        raise ValidationError("Расход меньше точности учёта 0,001. Уточните единицу препарата.")
    amount(result, "Расчётный расход", allow_zero=True)
    calculation["quantity"] = number(result)
    return rule.product, result, calculation
