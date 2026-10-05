from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


def amount(value, label="Вес", *, allow_zero=False):
    try:
        result = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"{label}: введите число.")
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise ValidationError(f"{label}: нужно {'неотрицательное' if allow_zero else 'положительное'} число.")
    if result > Decimal("999999999.999") or result.as_tuple().exponent < -3:
        raise ValidationError(f"{label}: не более 9 цифр до запятой и 3 после неё.")
    return result


def count(value, label="Количество", *, allow_zero=False):
    result = amount(value, label, allow_zero=allow_zero)
    if result != result.to_integral_value() or result > 1000000:
        raise ValidationError(f"{label}: требуется целое число не больше 1000000.")
    return int(result)


def rows(value):
    if not isinstance(value, list) or not value or len(value) > 500:
        raise ValidationError("Добавьте от 1 до 500 строк.")
    if any(not isinstance(row, dict) for row in value):
        raise ValidationError("Некорректный формат строк.")
    return value
