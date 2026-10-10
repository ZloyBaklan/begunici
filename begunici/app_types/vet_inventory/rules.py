"""User-entered accounting estimates; these rules never prescribe treatment."""
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from begunici.app_types.veterinary.vet_models import VeterinaryCare, WeightRecord
from begunici.app_types.inventory.validation import amount
from .models import VetNorm, VetProduct, VetSettings
from .permissions import require_treat
from .services import audit, number


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
def save_rule(user, care_id, revision, product_id, mode, rate, bands):
    require_treat(user)
    VetSettings.objects.select_for_update().get(pk=1)
    care = VeterinaryCare.objects.get(pk=care_id)
    rule = VetNorm.objects.filter(care=care).first()
    if str(rule.revision if rule else 0) != str(revision):
        raise ValidationError("Норма уже изменена. Обновите страницу.")
    try:
        product = VetProduct.objects.filter(pk=product_id).first()
    except (ValueError, TypeError):
        product = None
    if not product or mode not in dict(VetNorm._meta.get_field("mode").choices):
        raise ValidationError("Выберите препарат и способ расчёта.")
    clean_rate = None if mode == "bands" else amount(rate, "Норма", allow_zero=True)
    clean_rows = clean_bands(bands) if mode == "bands" else []
    before = rule_data(rule) if rule else None
    if rule is None:
        rule = VetNorm(care=care, revision=0)
    rule.product, rule.mode, rule.rate, rule.bands = product, mode, clean_rate, clean_rows
    rule.revision += 1
    rule.save()
    audit(user, "Изменена норма обработки", care=care.pk, before=before, after=rule_data(rule))
    return rule


def rule_data(rule):
    return {"product": rule.product_id, "name": rule.product.name, "unit": rule.product.get_unit_display(),
            "mode": rule.mode, "mode_label": rule.get_mode_display(),
            "rate": number(rule.rate) if rule.rate is not None else "", "bands": rule.bands, "revision": rule.revision}


def estimate(veterinary):
    rule = VetNorm.objects.select_related("product").filter(care_id=veterinary.veterinary_care_id).first()
    if rule is None:
        raise ValidationError("Для этой обработки ещё не задан препарат и норма расхода.")
    calculation = rule_data(rule)
    if rule.mode == "head":
        result = rule.rate
    else:
        record = WeightRecord.objects.filter(tag_id=veterinary.tag_id,
            weight_date__lte=veterinary.get_care_date(), weight__gt=0).order_by("-weight_date", "-pk").first()
        if record is None:
            raise ValidationError("Нет взвешивания на дату обработки. Укажите фактический расход вручную.")
        calculation.update(weight=number(record.weight), weight_date=record.weight_date.isoformat())
        if rule.mode == "weight":
            result = record.weight * rule.rate
        else:
            band = next((b for b in rule.bands if Decimal(b["from"]) <= record.weight
                         and (not b["to"] or record.weight < Decimal(b["to"]))), None)
            if band is None:
                raise ValidationError("Вес животного не попал в заданные диапазоны. Уточните расход вручную.")
            result = Decimal(band["amount"])
    result = result.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    amount(result, "Расчётный расход", allow_zero=True)
    calculation["quantity"] = number(result)
    return rule.product, result, calculation
