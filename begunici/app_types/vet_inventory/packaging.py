"""Physical package allocation; all writes share the medicine ledger lock."""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError

from .models import VetMovement, VetStockLot

ZERO = Decimal(0)


def sealed(lot):
    return lot.remaining // lot.capacity if lot.capacity else lot.packages


def lot_order(lot):
    return (lot.receipt.document.date if lot and lot.receipt_id else date.min, lot.pk if lot else 0)


def order_lots(lots):
    return sorted(lots, key=lot_order)


def ensure_lots(product, quantity, packages):
    lots = order_lots(VetStockLot.objects.select_for_update().filter(product=product).prefetch_related("receipt__document"))
    if not lots and (quantity or packages):
        # Legacy stock remains unclassified: its package size is not guessed.
        lots = [VetStockLot.objects.create(product=product, initial=quantity,
            remaining=quantity, packages=packages)]
    if sum((lot.remaining for lot in lots), ZERO) != quantity or sum((sealed(lot) for lot in lots), ZERO) != packages:
        raise ValidationError(f"{product.name}: остатки фасовок не совпадают с учётом. Требуется сверка.")
    return lots


def grouped_stock():
    result = defaultdict(list)
    for lot in VetStockLot.objects.filter(remaining__gt=0).select_related("product"):
        result[lot.product_id].append(lot)
    return result


def describe(lots):
    groups = {}
    unclassified = ZERO
    for lot in lots:
        if not lot.capacity:
            unclassified += lot.remaining
            continue
        row = groups.setdefault(lot.capacity, {"capacity": lot.capacity, "sealed": ZERO, "opened": ZERO})
        row["sealed"] += sealed(lot)
        row["opened"] += lot.remaining % lot.capacity
    return list(groups.values()), unclassified


def receive(product, lines):
    allocations = []
    for line in lines:
        capacity = Decimal(line["package_size"]) if line.get("package_size") else None
        qty, packs = Decimal(line["amount"]), Decimal(line["packages"])
        lot = VetStockLot.objects.create(product=product,
            capacity=capacity, initial=qty, remaining=qty, packages=packs)
        allocations.append({"lot": lot.pk, "amount": str(qty), "packages": str(packs)})
    return allocations


def consume(lots, lines):
    allocations = []

    def take(lot, qty, packs=ZERO):
        before = sealed(lot)
        lot.remaining -= qty
        if not lot.capacity:
            lot.packages -= packs
        consumed_packs = before - sealed(lot)
        lot.save(update_fields=["remaining", "packages"])
        allocations.append({"lot": lot.pk, "amount": str(qty), "packages": str(consumed_packs)})

    for line in lines:
        needed, requested_packs = Decimal(line["amount"]), Decimal(line["packages"])
        capacity = Decimal(line["package_size"]) if line.get("package_size") else None
        if capacity and requested_packs:
            for lot in lots:
                if lot.capacity == capacity and needed:
                    qty = min(needed, sealed(lot) * capacity)
                    if qty:
                        take(lot, qty)
                        needed -= qty
            if needed:
                raise ValidationError(f"{line['name']}: недостаточно закрытых упаковок выбранной фасовки.")
            continue
        # Every opened container is used before opening a sealed one.
        for lot in lots:
            if needed and lot.capacity and lot.remaining % lot.capacity:
                qty = min(needed, lot.remaining % lot.capacity)
                take(lot, qty)
                needed -= qty
        for lot in lots:
            if needed and lot.remaining:
                qty = min(needed, lot.remaining)
                take(lot, qty)
                needed -= qty
        if needed:
            raise ValidationError(f"{line['name']}: недостаточно содержимого упаковок.")
        if requested_packs:
            # Old documents accounted packages independently of their content.
            for lot in lots:
                if requested_packs and not lot.capacity:
                    packs = min(requested_packs, lot.packages)
                    take(lot, ZERO, packs)
                    requested_packs -= packs
            if requested_packs:
                raise ValidationError(f"{line['name']}: для списания целых упаковок укажите их размер.")
    return allocations


def reverse_allocations(original, product, sign):
    allocations = []
    for entry in reversed(original.allocations):
        lot = VetStockLot.objects.select_for_update().get(pk=entry["lot"], product=product)
        qty, packs = Decimal(entry["amount"]), Decimal(entry["packages"])
        before = sealed(lot)
        if sign < 0:
            if lot.remaining != lot.initial or (not lot.capacity and lot.packages != packs):
                raise ValidationError(f"{product.name}: приход уже использован. Сначала сторнируйте связанный расход.")
            lot.remaining = ZERO
            lot.packages = ZERO
        else:
            lot.remaining += qty
            if not lot.capacity:
                lot.packages += packs
        lot.save(update_fields=["remaining", "packages"])
        changed = (sealed(lot) - before) * sign
        allocations.append({"lot": lot.pk, "amount": str(qty), "packages": str(changed)})
    return allocations
