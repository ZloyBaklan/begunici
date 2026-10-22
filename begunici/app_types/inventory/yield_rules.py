"""Anatomical count checks, shared by receipt and cutting commands."""
from collections import defaultdict

from django.core.exceptions import ValidationError


def validate_parts(outputs, *, tag="", fraction=1, allow_carcass=True):
    totals = defaultdict(int)
    products = {}
    for product, row in outputs:
        totals[product.code] += row["quantity"]
        products[product.code] = product
    meat = {code for code, product in products.items() if product.category == "meat"}
    carcasses, halves = totals["carcass"], totals["half"]
    if carcasses and (not allow_carcass or meat - {"carcass"}):
        raise ValidationError(f"{tag}: нельзя одновременно принять тушу и её мясные части. Субпродукты добавляются отдельно.")
    if carcasses > fraction or halves > 2 * fraction:
        raise ValidationError(f"{tag}: превышено количество туш или полутуш.")
    remaining = fraction - halves / 2
    if halves and remaining == 0 and meat - {"half"}:
        raise ValidationError(f"{tag}: две полутуши уже содержат все мясные части.")
    for code, product in products.items():
        if code in {"carcass", "half"} or product.parts_per_animal is None:
            continue
        share = remaining if product.category == "meat" else fraction
        maximum = int(product.parts_per_animal * share)
        if totals[code] > maximum:
            raise ValidationError(f"{tag}: «{product.name}» — доступно не более {maximum} шт. с учётом полутуш и брака.")
