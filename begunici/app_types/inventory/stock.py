import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from .bridges import validate_case_source
from .models import AuditEvent, Product, StockLot, StockMovement
from .permissions import require_inventory
from .validation import amount, count, rows


def balance(lot):
    totals = lot.movements.aggregate(weight=Sum("weight"), quantity=Sum("quantity"))
    return totals["weight"] or Decimal(0), totals["quantity"] or 0


def available_lots():
    return StockLot.objects.select_related("animal", "animal__receipt", "product").annotate(
        available_weight=Sum("movements__weight"), available_quantity=Sum("movements__quantity"),
    ).filter(available_weight__gt=0).order_by("animal__tag_number", "id")


def validate_withdrawal(lot, weight, quantity):
    stock_weight, stock_quantity = balance(lot)
    if weight > stock_weight or quantity > stock_quantity:
        raise ValidationError(f"{lot.animal.tag_number}, {lot.product.name}: на складе только {stock_weight} кг / {stock_quantity} шт.")
    if lot.product.counted:
        if quantity <= 0:
            raise ValidationError("Для штучной продукции укажите количество.")
        if (weight == stock_weight) != (quantity == stock_quantity):
            raise ValidationError("Нельзя списать все килограммы, оставив штуки, или все штуки, оставив килограммы.")
    elif quantity:
        raise ValidationError("Для весовой продукции количество штук должно быть нулевым.")
    if lot.product.code == "live" and (weight != stock_weight or quantity != 1):
        raise ValidationError("Животное реализуется целиком: одна голова и вся учтённая масса.")
    validate_case_source(lot.animal)


@transaction.atomic
def cut_lot(user, lot_id, *, weight, quantity, outputs, loss_weight="0", reason="", expected_balance=None):
    require_inventory(user)
    lot = StockLot.objects.select_for_update().get(pk=lot_id)
    if expected_balance is not None:
        expected = (amount(expected_balance[0], allow_zero=True), count(expected_balance[1], allow_zero=True))
        if balance(lot) != expected:
            raise ValidationError("Остаток изменился после открытия разделки. Обновите страницу: операция могла быть уже проведена.")
    if lot.product.category != "meat":
        raise ValidationError("Разделка доступна только для мясной продукции.")
    weight, quantity = amount(weight), count(quantity, allow_zero=not lot.product.counted)
    validate_withdrawal(lot, weight, quantity)
    loss = amount(loss_weight, "Потери", allow_zero=True)
    if loss and not str(reason).strip():
        raise ValidationError("Укажите причину потерь при разделке.")
    product_map = {product.code: product for product in Product.objects.filter(category="meat")}
    clean, seen = [], set()
    for row in rows(outputs):
        product = product_map.get(row.get("product"))
        if not product or product.code == lot.product.code or product.code == "carcass":
            raise ValidationError("Выберите новую номенклатуру разделки; собрать тушу обратно нельзя.")
        if product.code in seen:
            raise ValidationError("Объедините одинаковые части в одну строку.")
        seen.add(product.code)
        if product.code == "half" and lot.product.code != "carcass":
            raise ValidationError("Полутуши можно получить только из туши.")
        qty = count(row.get("quantity", 0), allow_zero=not product.counted)
        if not product.counted and qty:
            raise ValidationError("Весовая продукция учитывается в килограммах без штук.")
        if product.code == "half" and qty > 2 * quantity:
            raise ValidationError("Из одной туши можно получить не более двух полутуш.")
        clean.append((product, amount(row.get("weight")), qty))
    if "half" in seen and len(seen) > 1:
        raise ValidationError("Сначала разделите тушу на полутуши, затем нужную полутушу на части.")
    if sum((item[1] for item in clean), Decimal(0)) + loss != weight:
        raise ValidationError("Вес полученных частей плюс потери должен точно равняться весу, переданному в разделку.")
    operation = uuid.uuid4()
    StockMovement.objects.create(lot=lot, kind="cut_out", weight=-weight, quantity=-quantity,
                                 operation=operation, reason=str(reason).strip(), created_by=user)
    new_lots = []
    for product, output_weight, qty in clean:
        child = StockLot.objects.create(animal=lot.animal, product=product, parent=lot)
        StockMovement.objects.create(lot=child, kind="cut_in", weight=output_weight, quantity=qty, operation=operation, created_by=user)
        new_lots.append(child)
    AuditEvent.objects.create(actor=user, document=lot.animal.receipt, action="cut", data={
        "operation": str(operation), "source_lot": lot.pk, "weight": str(weight), "quantity": quantity,
        "outputs": [child.pk for child in new_lots], "loss_weight": str(loss), "reason": str(reason).strip(),
    })
    return new_lots
