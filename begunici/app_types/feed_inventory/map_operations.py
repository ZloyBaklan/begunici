"""Map-only HTTP bridge to the existing barn feed ledger."""
import json
import hashlib
import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from begunici.app_types.inventory.permissions import require_inventory
from begunici.app_types.inventory.documents import read_upload

from . import barns, services, map_closing


def _quantities(lines):
    return sorted((line["product"], Decimal(line["amount"]), Decimal(line["packages"])) for line in lines)


@require_POST
def save(request):
    try:
        barns.require_supply(request.user)
        kind = request.POST.get("kind")
        if kind not in {"delivery", "writeoff", "close"}:
            raise ValidationError("Выберите поставку, списание или фактический расход.")
        if kind in {"writeoff", "close"}:
            require_inventory(request.user)
        if request.POST.get("verified") != "yes":
            raise ValidationError("Подтвердите проверку количеств.")
        try:
            lines = json.loads(request.POST.get("lines", ""))
        except (ValueError, TypeError):
            raise ValidationError("Проверьте список кормов и количества.")
        if not isinstance(lines, list) or any(not isinstance(line, dict) for line in lines):
            raise ValidationError("Проверьте список кормов и количества.")
        if kind == "close":
            doc = map_closing.confirm(request, lines)
            return JsonResponse({"message": f"Фактический расход за {doc.date:%Y-%m} подтверждён · Овчарня {doc.barn}. Остатки обновлены.",
                "document": doc.pk, "token": str(uuid.uuid4())})
        note = request.POST.get("note", "").strip()
        if not note and kind == "delivery":
            note = "Поставка на овчарню с карты овчарен"
        lines = services.normalize_lines(lines)
        day = services.valid_date(request.POST.get("date"))
        upload = request.FILES.get("file")
        checksum = ""
        if upload:
            content, _, _ = read_upload(upload)
            checksum = hashlib.sha256(content).hexdigest()
            upload.seek(0)
        doc = barns.move(request.user, request.POST.get("barn"), kind, day.isoformat(),
            lines, note, request.POST.get("token"), upload)
        # A retry may confirm an earlier successful request, never edited figures.
        if (doc.date != day or doc.payload["note"] != note or doc.sha256 != checksum
                or _quantities(doc.payload["lines"]) != _quantities(lines)):
            raise ValidationError(f"Операция № {doc.pk} уже проведена с другими данными. Обновите карту перед новой операцией.")
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
    action = "Поставка проведена" if kind == "delivery" else "Списание проведено"
    return JsonResponse({"message": f"{action} · № {doc.pk} · Овчарня {doc.barn}. Остатки обновлены.",
        "document": doc.pk, "token": str(uuid.uuid4())})
