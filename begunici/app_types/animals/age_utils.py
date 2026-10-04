from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta
from django.utils import timezone


def as_local_date(value):
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def get_age_delta(birth_date, reference_date=None):
    birth_date = as_local_date(birth_date)
    reference_date = timezone.localdate() if reference_date is None else as_local_date(reference_date)
    if not birth_date or not reference_date or birth_date > reference_date:
        return None
    return relativedelta(reference_date, birth_date)


def calculate_age_months(birth_date, reference_date=None):
    delta = get_age_delta(birth_date, reference_date)
    if delta is None:
        return None
    months = Decimal(delta.years * 12 + delta.months) + Decimal(delta.days) / 30
    return months.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def format_age(birth_date, reference_date=None):
    delta = get_age_delta(birth_date, reference_date)
    if delta is None:
        return None
    months = delta.years * 12 + delta.months
    if not months and not delta.days:
        return "0 мес."
    if not months:
        return f"{delta.days} сут."
    if not delta.days:
        return f"{months} мес."
    return f"{months} мес. ({delta.days} сут.)"


def age_months_for_export(birth_date, reference_date=None):
    age = calculate_age_months(birth_date, reference_date)
    return age if age is not None else "-"


def _parse_age_bound(value):
    try:
        value = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return value if value.is_finite() else None


def _latest_birth_date_for_age(reference_date, target_age, strict=False):
    # Search once per bound, then filter in SQL by birth_date. This keeps calendar
    # month ends and rounding identical to the displayed numeric age without
    # loading animals into memory.
    low = 0
    high = reference_date.toordinal() + 1
    while high - low > 1:
        middle = (low + high) // 2
        age = calculate_age_months(date.fromordinal(middle), reference_date)
        matches = age > target_age if strict else age >= target_age
        if matches:
            low = middle
        else:
            high = middle
    return date.fromordinal(low) if low else None


def filter_queryset_by_age(queryset, age_min=None, age_max=None, reference_date=None):
    age_min = _parse_age_bound(age_min)
    age_max = _parse_age_bound(age_max)
    if age_min is None and age_max is None:
        return queryset
    reference_date = timezone.localdate() if reference_date is None else as_local_date(reference_date)
    queryset = queryset.filter(birth_date__lte=reference_date)
    if age_min is not None:
        latest_birth_date = _latest_birth_date_for_age(reference_date, age_min)
        if latest_birth_date is None:
            return queryset.none()
        queryset = queryset.filter(birth_date__lte=latest_birth_date)
    if age_max is not None:
        too_old_birth_date = _latest_birth_date_for_age(reference_date, age_max, strict=True)
        if too_old_birth_date is not None:
            queryset = queryset.filter(birth_date__gt=too_old_birth_date)
    return queryset
