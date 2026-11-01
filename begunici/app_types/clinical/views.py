import json
import uuid
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from rest_framework.exceptions import ValidationError as APIValidationError
from begunici.app_types.veterinary.vet_models import Place, Status
from begunici.app_types.animals.models import ARCHIVE_STATUS_NAMES, ARCHIVE_DEATH_REASONS
from begunici.app_types.animals.status_logic import get_animal_status_validation_error
from begunici.app_types.vet_inventory.services import stock_rows
from .models import Episode
from .permissions import access_required, can_admit, can_manage
from . import services


def context(request, **kwargs):
    return {"clinical_can_manage": can_manage(request.user), "clinical_can_admit": can_admit(request.user), "today": timezone.localdate(), **kwargs}


def animal_map(tag_ids):
    result = {}
    for model in services.ANIMALS:
        result.update({a.tag_id: a for a in model.objects.filter(tag_id__in=tag_ids).select_related("tag", "place", "animal_status")})
    return result


@require_GET
@access_required
def journal(request):
    archive = request.GET.get("archive") == "1"
    q = request.GET.get("q", "").strip()[:200]
    episodes = Episode.objects.filter(closed_on__isnull=not archive).select_related("tag", "expense_document", "closed_by").prefetch_related("events__doses")
    if q:
        episodes = episodes.filter(Q(tag__tag_number__icontains=q) | Q(diagnosis__icontains=q) | Q(snapshot__tag__icontains=q) | Q(tag__maker__rshn_tag__icontains=q) | Q(tag__ram__rshn_tag__icontains=q) | Q(tag__ewe__rshn_tag__icontains=q) | Q(tag__sheep__rshn_tag__icontains=q))
    if request.GET.get("pending") == "1":
        episodes = episodes.filter(expense_document__state="draft")
    page = Paginator(episodes, 25).get_page(request.GET.get("page"))
    animals = animal_map([e.tag_id for e in page])
    histories = dict(Episode.objects.filter(tag_id__in=animals).values("tag_id").annotate(n=Count("pk")).values_list("tag_id", "n"))
    for index, episode in enumerate(page, start=page.start_index()):
        episode.row_number = index
        episode.animal = animals.get(episode.tag_id)
        episode.display_snapshot = services.animal_snapshot(episode.animal) if episode.animal and not episode.closed_on else episode.snapshot
        episode.previous_count = histories.get(episode.tag_id, 1) - 1
        episode.recent_events = [event for event in episode.events.all() if event.kind == "care"][-3:]
    return render(request, "clinical/journal.html", context(request, episodes=page, archive=archive, q=q, pending=request.GET.get("pending") == "1"))


@require_GET
@access_required
def detail(request, pk):
    episode = get_object_or_404(Episode.objects.select_related("tag", "closed_by", "expense_document").prefetch_related("events__doses", "events__created_by"), pk=pk)
    animal = animal_map([episode.tag_id]).get(episode.tag_id)
    statuses = []
    if animal:
        statuses = [s for s in Status.objects.order_by("status_type") if not get_animal_status_validation_error(s, animal.get_animal_type(), allow_archive=True)]
    previous = Episode.objects.filter(tag_id=episode.tag_id).exclude(pk=pk) if episode.tag_id else Episode.objects.none()
    return render(request, "clinical/detail.html", context(request, episode=episode, animal=animal, snapshot=services.animal_snapshot(animal) if animal and not episode.closed_on else episode.snapshot, totals=services.totals(episode), previous=previous, statuses=statuses, places=Place.objects.order_by("sheepfold"), death_reasons=ARCHIVE_DEATH_REASONS, archive_statuses=list(ARCHIVE_STATUS_NAMES), products=stock_rows()))


@require_GET
@access_required
def care(request):
    raw_ids = request.GET.get("episodes", "").split(",")
    try:
        ids = sorted({int(pk) for pk in raw_ids if pk})
    except ValueError:
        ids = []
    episodes = list(Episode.objects.filter(pk__in=ids, closed_on__isnull=True).select_related("tag"))
    if len(ids) != len(episodes) or not 1 <= len(ids) <= 200:
        return render(request, "clinical/error.html", context(request, error="Выберите от 1 до 200 животных в действующем журнале."), status=400)
    return render(request, "clinical/care.html", context(request, episodes=episodes, products=stock_rows(), form_token=str(uuid.uuid4())))


@require_POST
@access_required
def command(request, action, pk=None):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Некорректная форма запроса."}, status=400)
    try:
        if action == "care":
            services.add_care(request.user, data.get("episodes"), data.get("date"), data.get("note"), data.get("lines", []), data.get("mode"), data.get("token"))
            url = reverse("clinical:journal")
        elif action == "intake":
            services.update_intake(request.user, pk, data.get("revision"), data.get("diagnosis"), data.get("admitted_on"), data.get("place"), data.get("confirm_group_move") is True)
            url = reverse("clinical:detail", args=[pk])
        elif action == "close":
            if data.get("confirm_expense") is not True:
                raise ValidationError("Подтвердите проверку фактического расхода препаратов.")
            services.close_episode(request.user, pk, data.get("revision"), data.get("outcome"), data.get("closed_on"), data.get("lines", []), data.get("reason"), data.get("status_id"), data.get("confirm_status") is True, data.get("archive"))
            url = reverse("clinical:detail", args=[pk])
        elif action == "reconcile":
            services.reconcile(request.user, pk)
            url = reverse("clinical:detail", args=[pk])
        else:
            return JsonResponse({"error": "Неизвестное действие."}, status=404)
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
    except APIValidationError as exc:
        return JsonResponse({"error": exc.detail}, status=400)
    except Episode.DoesNotExist:
        return JsonResponse({"error": "Запись журнала не найдена."}, status=404)
    return JsonResponse({"url": url})
