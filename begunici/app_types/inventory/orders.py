from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from .animal_types import ANIMAL_TYPE_LABELS, ANIMAL_TYPE_SEX
from .models import AuditEvent, Order, OrderLine, Product, StockMovement
from .permissions import require_inventory
from .validation import amount, count, rows


def purity(value):
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        raise ValidationError("Кровность должна быть числом от 0 до 100.")
    if not result.is_finite() or not 0 <= result <= 100 or result.as_tuple().exponent < -5:
        raise ValidationError("Кровность должна быть от 0 до 100, максимум 5 знаков после запятой.")
    return result


@transaction.atomic
def create_order(user, data, *, external_key=None):
    """Future website adapter calls this function with a stable external key."""
    require_inventory(user)
    if external_key:
        existing = Order.objects.filter(external_key=external_key).first()
        if existing:
            return existing
    kind, customer = data.get("kind"), str(data.get("customer", "")).strip()
    if kind not in {"live", "meat"} or not customer or len(customer) > 200:
        raise ValidationError("Выберите тип заявки и укажите получателя (до 200 символов).")
    order = Order.objects.create(
        kind=kind, customer=customer, contact=str(data.get("contact", ""))[:200],
        note=str(data.get("note", ""))[:5000],
        required_heads=count(data.get("required_heads", 0), "Количество животных", allow_zero=True),
        external_key=external_key, created_by=user,
    )
    product_map = {product.code: product for product in Product.objects.all()}
    for item in rows(data.get("lines")):
        product = product_map.get(item.get("product"))
        if not product or (product.category == "live") != (kind == "live"):
            raise ValidationError("Номенклатура не соответствует типу заявки.")
        weight = amount(item.get("weight", 0), allow_zero=True)
        quantity = count(item.get("quantity", 0), allow_zero=True)
        if not weight and not quantity:
            raise ValidationError("Для каждой строки заявки укажите вес и/или количество.")
        if quantity and not product.counted:
            raise ValidationError("Фарш учитывается по весу. Количество штук оставьте нулевым.")
        sex = item.get("sex", "")
        if sex not in {"", "male", "female"}:
            raise ValidationError("Неизвестный пол животного.")
        animal_type = item.get("animal_type", "")
        if animal_type not in {"", *ANIMAL_TYPE_LABELS}:
            raise ValidationError("Неизвестный тип животного.")
        if animal_type and sex and ANIMAL_TYPE_SEX[animal_type] != sex:
            raise ValidationError("Тип животного противоречит прежнему требованию заявки.")
        limits = {}
        for key in ("age_min", "age_max"):
            limits[key] = count(item[key], "Возраст в месяцах", allow_zero=True) if item.get(key) not in (None, "") else None
        for key in ("purity_min", "purity_max"):
            limits[key] = purity(item.get(key))
        if kind == "meat" and (animal_type or sex or any(value is not None for value in limits.values())):
            raise ValidationError("Тип животного, возраст и кровность задаются для заявок живьём.")
        for prefix in ("age", "purity"):
            lower, upper = limits[prefix + "_min"], limits[prefix + "_max"]
            if lower is not None and upper is not None and lower > upper:
                raise ValidationError("Нижняя граница не может быть выше верхней.")
        OrderLine.objects.create(order=order, product=product, weight=weight, quantity=quantity,
                                 animal_type=animal_type, sex=sex, **limits)
    AuditEvent.objects.create(order=order, actor=user, action="order_created", data={"external_key": external_key})
    return order


def quality_issues(line, case):
    data = case.snapshot
    issues = []
    if line.animal_type and case.animal_type != line.animal_type:
        issues.append(f"тип животного (нужен: {line.type_requirement})")
    if line.sex and data.get("sex") != line.sex:
        issues.append(f"тип животного (нужен: {line.type_requirement})")
    for label, value, lower, upper in (
        ("возраст", data.get("age_months"), line.age_min, line.age_max),
        ("кровность", data.get("dorper_percentage"), line.purity_min, line.purity_max),
    ):
        if lower is None and upper is None:
            continue
        if value is None or value == "":
            issues.append(f"{label} не указан")
        elif (lower is not None and Decimal(str(value)) < lower) or (upper is not None and Decimal(str(value)) > upper):
            issues.append(label)
    return issues


def fulfillment(order, extra=None):
    """Accumulate allocations across confirmed, non-reversed invoices only.

    Allocation is per order line, so a delivery cannot cover two requirements.
    Units/weight exceeding one line never compensate another missing SKU.
    """
    lines = {line.pk: line for line in order.lines.select_related("product")}
    totals = {key: {"weight": Decimal(0), "quantity": 0, "issues": []} for key in lines}
    heads = set()
    movements = StockMovement.objects.filter(
        document__order=order, document__state="confirmed", kind="sale",
    ).select_related("lot__animal", "lot__product", "order_line")
    entries = [(m.order_line_id, m.lot, -m.weight, -m.quantity) for m in movements]
    entries.extend(extra or [])
    for line_id, lot, weight, quantity in entries:
        if line_id not in lines:
            continue
        line = lines[line_id]
        issues = quality_issues(line, lot.animal) if order.kind == "live" else []
        if issues:
            totals[line_id]["issues"].append(f"{lot.animal.tag_number}: {', '.join(issues)}")
            continue
        totals[line_id]["weight"] += weight
        totals[line_id]["quantity"] += quantity
        heads.add(lot.animal_id)
    report = []
    missing = []
    for key, line in lines.items():
        actual = totals[key]
        weight_ok = actual["weight"] >= line.weight
        quantity_ok = actual["quantity"] >= line.quantity
        complete = weight_ok and quantity_ok and not actual["issues"]
        if not complete:
            details = []
            if not weight_ok:
                details.append(f"не хватает {line.weight - actual['weight']} кг")
            if not quantity_ok:
                details.append(f"не хватает {line.quantity - actual['quantity']} шт.")
            details.extend(actual["issues"])
            missing.append(f"{line.product.name}: {'; '.join(details)}")
        report.append({
            "id": key, "product": line.product.name, "product_code": line.product.code,
            "weight_required": str(line.weight), "weight_actual": str(actual["weight"]),
            "quantity_required": line.quantity, "quantity_actual": actual["quantity"],
            "weight_ok": weight_ok, "quantity_ok": quantity_ok,
            "issues": actual["issues"], "complete": complete,
        })
    if len(heads) < order.required_heads:
        missing.append(f"Количество животных: {len(heads)} из {order.required_heads}.")
    return {"complete": not missing and bool(lines), "lines": report, "missing": missing,
            "heads_actual": len(heads), "heads_required": order.required_heads, "has_deliveries": bool(entries)}


def refresh_state(order, *, close=False):
    report = fulfillment(order)
    if close and not report["complete"]:
        raise ValidationError("Заявку нельзя закрыть: " + "; ".join(report["missing"]))
    order.state = ("closed" if close else "fulfilled") if report["complete"] else ("partial" if report["has_deliveries"] else "open")
    order.save(update_fields=["state"])
    return report


@transaction.atomic
def close_order(user, order_id):
    require_inventory(user)
    order = Order.objects.select_for_update().get(pk=order_id)
    refresh_state(order, close=True)
    AuditEvent.objects.create(order=order, actor=user, action="order_closed")
    return order
