"""Catalog and quantity adapters; historical document totals keep their meaning."""
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from .models import FeedProduct
from begunici.app_types.inventory.validation import amount


def configure(product, *, package_weight=None, plan_product=None):
    if product.variants.exclude(unit=product.unit, category=product.category).exists():
        raise ValidationError("Единица и категория общего типа должны совпадать со связанными позициями.")
    if package_weight is not None:
        product.package_weight = amount(package_weight, "Вес упаковки") if package_weight != "" else None
        if product.package_weight and (not product.package or product.unit != "kg"):
            raise ValidationError("Вес упаковки задаётся для позиции в кг с указанной упаковкой.")
    if plan_product is not None:
        try:
            parent = FeedProduct.objects.get(pk=int(plan_product)) if plan_product else None
        except (ValueError, TypeError, FeedProduct.DoesNotExist):
            raise ValidationError("Выберите тип корма из списка.")
        if parent and (parent.pk == product.pk or parent.plan_product_id or parent.unit != product.unit or parent.category != product.category or product.variants.exists()):
            raise ValidationError("Выберите самостоятельный тип с такой же категорией и единицей. Вложенные группы не поддерживаются.")
        if (parent.pk if parent else None) != product.plan_product_id and (product.movements.exists() or product.norms.filter(per_head__gt=0).exists()):
            raise ValidationError("Тип уже используется в движениях или нормах. Создайте новую позицию нужного типа.")
        product.plan_product = parent
    product.save(update_fields=["package_weight", "plan_product"])


def line_total(row, product):
    quantity = amount(row.get("amount") or 0, "Количество", allow_zero=True)
    packages = amount(row.get("packages") or 0, "Упаковки", allow_zero=True)
    unit_amount = row.get("unit_amount")
    extra = {}
    if unit_amount not in (None, ""):
        unit_amount = amount(unit_amount, "Количество на упаковку")
        if product.unit != "kg" or not product.package:
            raise ValidationError("Вес на упаковку доступен для упакованной продукции в кг.")
        if packages:
            quantity = amount((unit_amount * packages).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP), "Итоговое количество")
            extra["unit_amount"] = format(unit_amount, "f")
    return quantity, packages, extra


def group_map():
    return {p.pk: p.plan_product_id or p.pk for p in FeedProduct.objects.all()}
