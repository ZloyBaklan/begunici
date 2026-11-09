"""Monthly consumption in the map dialog, using the existing closing ledger."""
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from begunici.app_types.inventory.permissions import require_inventory
from begunici.app_types.inventory.validation import amount
from . import barns, services
from .models import BarnFeedDocument, BarnFeedPeriod, FeedSettings
from .plan import number


@require_GET
def details(request):
    try:
        barns.require_supply(request.user, write=False)
        require_inventory(request.user, write=False)
        barn = barns.barn_number(request.GET.get("barn"))
        month = barns.month_date(request.GET.get("month"))
        if barns.month_end(month) >= timezone.localdate():
            raise ValidationError("Фактический расход можно подтвердить после окончания месяца.")
        period = BarnFeedPeriod.objects.filter(barn=barn, month=month).select_related("closing").first()
        ready, rows = False, []
        if not period:
            message = "За этот месяц ещё не зафиксирован план. Историческое поголовье автоматически не восстанавливается."
        elif period.closing_id:
            message = "Фактический расход за этот месяц уже подтверждён. Ниже сохранённые результаты."
            for line in period.closing.payload["lines"]:
                rows.append({"product": line["product"], "name": line["name"], "unit": line["unit"], "package": line["package"],
                    "available": line["available"], "packages": number(Decimal(line["packages"]) + Decimal(line["closing_packages"])),
                    "remaining": line["closing"], "remaining_packages": line["closing_packages"]})
        else:
            earlier = BarnFeedPeriod.objects.filter(barn=barn, month__lt=month, closing__isnull=True).order_by("month").first()
            ready = earlier is None
            message = (f"Сначала подтвердите расход за {earlier.month:%Y-%m}." if earlier else
                "Укажите фактические остатки на конец выбранного месяца. Если всё съедено, отметьте «Всё израсходовано».")
            for row in barns.closing_rows(barn, month):
                product = row["product"]
                rows.append({"product": product.pk, "name": product.name, "unit": product.get_unit_display(), "package": product.package,
                    "available": number(row["available"]), "packages": number(row["packages"]), "remaining": "", "remaining_packages": ""})
        return JsonResponse({"ready": ready, "closed": bool(period and period.closing_id), "message": message, "rows": rows})
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)


@transaction.atomic
def confirm(request, lines):
    require_inventory(request.user)
    FeedSettings.objects.select_for_update().get(pk=1)
    barn = barns.barn_number(request.POST.get("barn"))
    month = barns.month_date(request.POST.get("month"))
    token = services.token(request.POST.get("token"))
    note = services.text(request.POST.get("note") or "Фактический расход подтверждён на карте овчарен", "Комментарий", 2000)
    existing = BarnFeedDocument.objects.filter(token=token).first()
    if existing and (existing.kind != "close" or existing.barn != barn or existing.created_by_id != request.user.pk
            or existing.payload.get("month") != month.isoformat() or BarnFeedDocument.objects.filter(reversal_of=existing).exists()):
        raise ValidationError("Этот идентификатор уже использован. Обновите карту перед новой операцией.")
    expected = {row["product"] for row in existing.payload["lines"]} if existing else {row["product"].pk for row in barns.closing_rows(barn, month)}
    if len(lines) > 200:
        raise ValidationError("Допускается не более 200 позиций.")
    values = {}
    for line in lines:
        try:
            pk = int(line["product"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Проверьте список кормов.")
        if str(pk) in values:
            raise ValidationError("Корм не должен повторяться в сверке.")
        values[str(pk)] = {"amount": amount(line.get("amount"), "Фактический остаток", allow_zero=True),
            "packages": amount(line.get("packages") or 0, "Оставшиеся упаковки", allow_zero=True)}
    if {int(pk) for pk in values} != expected:
        raise ValidationError("Список остатков изменился. Выберите овчарню и месяц заново, затем проверьте количества.")
    if existing and (existing.payload["note"] != note or any(
            values[str(row["product"])]["amount"] != Decimal(row["closing"]) or
            values[str(row["product"])]["packages"] != Decimal(row["closing_packages"]) for row in existing.payload["lines"])):
        raise ValidationError("Этот расход уже подтверждён с другими остатками. Обновите карту.")
    return barns.close_month(request.user, barn, month, values, note, token)
