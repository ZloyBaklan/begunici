"""Map-only HTTP bridge to the barn feed ledger."""
import json
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from begunici.app_types.inventory.permissions import require_inventory
from . import barns, map_closing


def read_list(value, message):
    try:
        rows = json.loads(value)
    except (ValueError, TypeError):
        raise ValidationError(message)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValidationError(message)
    return rows


@require_POST
def save(request):
    try:
        barns.require_supply(request.user)
        kind = request.POST.get("kind")
        if kind not in {"delivery", "writeoff", "close", "week"}:
            raise ValidationError("Выберите операцию с кормами.")
        if kind != "delivery":
            require_inventory(request.user)
        if request.POST.get("verified") != "yes":
            raise ValidationError("Подтвердите проверку количеств.")
        note = request.POST.get("note", "").strip()
        day = request.POST.get("date")
        token = request.POST.get("token")
        if kind == "delivery" and "deliveries" in request.POST:
            deliveries = read_list(request.POST["deliveries"], "Проверьте список овчарен для поставки.")
            documents = barns.deliver_batch(request.user, deliveries, day, note or "Поставка с карты овчарен", token)
            numbers = ", ".join(str(doc.barn) for doc in documents)
            return JsonResponse({"message": f"Поставка проведена. Остатки обновлены по овчарням: {numbers}.",
                "documents": [doc.pk for doc in documents], "token": str(uuid.uuid4())})
        lines = read_list(request.POST.get("lines"), "Проверьте список кормов и количества.")
        if kind in {"close", "week"}:
            doc = map_closing.confirm(request, lines, weekly=kind == "week")
            period = "за неделю" if kind == "week" else f"за {doc.date:%m.%Y}"
            action = f"Расход {period} подтверждён"
        else:
            if kind == "delivery" and not note:
                note = "Поставка на овчарню с карты овчарен"
            doc = barns.move(request.user, request.POST.get("barn"), kind, day, lines, note, token, request.FILES.get("file"))
            action = "Поставка проведена" if kind == "delivery" else "Списание проведено"
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
    return JsonResponse({"message": f"{action} · № {doc.pk} · Овчарня {doc.barn}. Остатки обновлены.",
        "document": doc.pk, "token": str(uuid.uuid4())})
