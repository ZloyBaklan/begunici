from decimal import Decimal, ROUND_HALF_UP

from .models import Product


def line_price(product, weight, quantity):
    """Return JSON-safe values captured when a document version is formed."""
    price = product.unit_price
    if product.category == "live" or price is None:
        return {"unit_price": None, "price_unit": None, "line_total": None}

    basis = quantity if product.price_unit == Product.PriceUnit.PIECE else weight
    total = None
    if weight not in (None, ""):
        total = (price * Decimal(basis)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"unit_price": str(price), "price_unit": product.price_unit,
            "line_total": str(total) if total is not None else None}
