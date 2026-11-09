"""Forecast and reconcile natural consumption from the map."""
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from begunici.app_types.inventory.permissions import require_inventory
from . import barn_forecast, barns
from .models import BarnFeedMovement, BarnFeedPeriod, FeedProduct
from .plan import number


def recorded_weekly_use(barn, month):
    totals = defaultdict(Decimal)
    for week in barns.active_weeks(barn).filter(date__range=(month, barns.month_end(month))):
        for line in week.payload["lines"]:
            totals[line["product"]] += Decimal(line["amount"])
    return totals


def append_recorded_only(rows, weekly_use):
    # A weekly reconciliation can exhaust an item before the monthly form is opened.
    missing = weekly_use.keys() - {row["product"] for row in rows}
    for product in FeedProduct.objects.filter(pk__in=missing):
        rows.append({"product": product.pk, "name": product.name, "unit": product.get_unit_display(),
            "package": product.package, "available": "0", "packages": "0", "remaining": "0",
            "remaining_packages": "0", "recorded_use": number(weekly_use[product.pk]),
            "actual_use": number(weekly_use[product.pk]), "recorded_only": True})


def reconciliation_details(barn, start, end, *, weekly=False):
    month = start.replace(day=1)
    period = BarnFeedPeriod.objects.filter(barn=barn, month=month).select_related("closing").first()
    weekly_use = {} if weekly else recorded_weekly_use(barn, month)
    document = (barns.active_weeks(barn).filter(date=end).first() if weekly else period.closing if period else None)
    result = {"start": start.isoformat(), "end": end.isoformat(), "closed": bool(document), "ready": False, "rows": []}
    if document:
        result["message"] = "Расход за этот период уже подтверждён. Ниже сохранённые результаты."
        for line in document.payload["lines"]:
            result["rows"].append({"product": line["product"], "name": line["name"], "unit": line["unit"],
                "package": line["package"], "available": line["available"],
                "packages": number(Decimal(line["packages"]) + Decimal(line["closing_packages"])),
                "remaining": line["closing"], "remaining_packages": line["closing_packages"],
                "actual_use": number(Decimal(line["amount"]) + weekly_use.get(line["product"], barns.ZERO)),
                "recorded_use": number(weekly_use.get(line["product"], barns.ZERO))})
        append_recorded_only(result["rows"], weekly_use)
        return result

    if not weekly and not period and not BarnFeedMovement.objects.filter(document__barn=barn, document__date__lte=end).exists():
        result["message"] = "За этот месяц ещё не зафиксирован кормовой план овчарни."
        return result
    earlier = BarnFeedPeriod.objects.filter(barn=barn, month__lt=month, closing__isnull=True).order_by("month").first()
    rows = barns.closing_rows(barn, start, end)
    if earlier:
        result["message"] = f"Сначала подтвердите расход за {earlier.month:%m.%Y}."
    elif weekly and period and period.closing_id:
        result["message"] = "Месяц уже закрыт. Расход за него можно посмотреть в месячной сверке."
    elif barns.active_weeks(barn).filter(date__gt=end).exists():
        result["message"] = "Сначала сторнируйте более позднюю недельную сверку."
    elif weekly and not rows:
        result["message"] = "За эту неделю нет кормов для сверки."
    else:
        result.update(ready=True, message="Сверьте расчёт с фактическим остатком на конец периода.")
    result["estimate"] = barn_forecast.consumption_estimate(barn, start, end, rows, period.plan if period else None)
    for row in rows:
        product = row["product"]
        recorded = weekly_use.get(product.pk, barns.ZERO)
        result["rows"].append({"product": product.pk, "name": product.name, "unit": product.get_unit_display(),
            "package": product.package, "available": number(row["available"]), "packages": number(row["packages"]),
            "remaining": "", "remaining_packages": "", "recorded_use": number(recorded),
            "estimated_use": number(row["estimated_use"] + recorded), "estimated_remaining": number(row["estimated_remaining"])})
    append_recorded_only(result["rows"], weekly_use)
    return result


@require_GET
def details(request):
    try:
        barns.require_supply(request.user, write=False)
        require_inventory(request.user, write=False)
        barn = barns.barn_number(request.GET.get("barn"))
        weekly = request.GET.get("kind") == "week"
        if weekly:
            start, end = barns.week_dates(request.GET.get("week"))
        else:
            start = barns.month_date(request.GET.get("month"))
            end = barns.month_end(start)
        if end >= timezone.localdate():
            raise ValidationError("Расход можно подтвердить после окончания периода.")
        return JsonResponse(reconciliation_details(barn, start, end, weekly=weekly))
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)


def confirm(request, lines, *, weekly=False):
    if len(lines) > 200:
        raise ValidationError("Допускается не более 200 позиций.")
    values = {}
    for line in lines:
        try:
            pk = str(int(line["product"]))
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Проверьте список кормов.")
        if pk in values:
            raise ValidationError("Корм не должен повторяться в сверке.")
        values[pk] = {"amount": line.get("amount"), "packages": line.get("packages")}
    close = barns.close_week if weekly else barns.close_month
    period = request.POST.get("week" if weekly else "month")
    return close(request.user, request.POST.get("barn"), period, values,
        request.POST.get("note") or "Фактический расход подтверждён на карте овчарен", request.POST.get("token"))
