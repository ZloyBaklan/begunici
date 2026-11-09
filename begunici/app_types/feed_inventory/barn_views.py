import uuid
from datetime import timedelta
from functools import wraps
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse, FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods
from django.utils import timezone
from io import BytesIO

from . import barn_forecast, barns, map_closing, views
from .models import FeedProduct, BarnFeedDocument, BarnFeedPeriod
from begunici.app_types.inventory.permissions import can_manage_inventory, require_inventory


def access(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        barns.require_supply(request.user, write=request.method not in {"GET", "HEAD", "OPTIONS"})
        try:
            return view(request, *args, **kwargs)
        except ValidationError as exc:
            return HttpResponseBadRequest("; ".join(exc.messages))
    return wrapped


def page(request, template, **context):
    return render(request, "feed_inventory/barns/" + template + ".html", {
        "section": "feeds", "can_finance": can_manage_inventory(request.user),
        "can_supply": barns.can_supply(request.user), **context})


def summary(request, barn):
    return barns.summary(barn, capture_plan=barns.can_supply(request.user))


@require_GET
@access
def overview(request):
    return page(request, "overview", barns=[summary(request, i) for i in range(1, 5)])


@require_GET
@access
def map_data(request):
    return JsonResponse({"barns": [summary(request, i) for i in range(1, 5)]})


@require_http_methods(["GET", "POST"])
@access
def detail(request, barn):
    barn = barns.barn_number(barn)
    if request.method == "POST":
        try:
            barns.reverse(request.user, request.POST.get("document"), request.POST.get("reason"))
            messages.success(request, "Сторно выполнено. История сохранена.")
            return redirect("feed_inventory:barn", barn=barn)
        except ValidationError as exc:
            views.error(request, exc)
    return page(request, "detail", summary=summary(request, barn), barn=barn,
        documents=BarnFeedDocument.objects.filter(barn=barn).select_related("created_by", "central_document"))


@require_http_methods(["GET", "POST"])
@access
def move(request, barn, kind):
    barn = barns.barn_number(barn)
    if kind not in {"delivery", "return", "writeoff"}:
        raise Http404
    if kind == "writeoff":
        require_inventory(request.user, write=request.method == "POST")
    products = list(FeedProduct.objects.all())
    if request.method == "POST":
        try:
            if request.POST.get("verified") != "yes":
                raise ValidationError("Подтвердите проверку количеств.")
            doc = barns.move(request.user, barn, kind, request.POST.get("date"), views.posted_lines(request, products),
                request.POST.get("note"), request.POST.get("token"), request.FILES.get("file"))
            messages.success(request, f"Операция № {doc.pk} проведена. Остатки обновлены.")
            return redirect("feed_inventory:barn", barn=barn)
        except ValidationError as exc:
            views.error(request, exc)
    return page(request, "move", barn=barn, kind=kind, form=request.POST,
        rows=views.editor_rows(request, products, show_available=kind == "delivery"), token=request.POST.get("token") or uuid.uuid4())


@require_http_methods(["GET", "POST"])
@access
def close(request, barn):
    require_inventory(request.user, write=request.method == "POST")
    barn = barns.barn_number(barn)
    previous = timezone.localdate().replace(day=1) - timedelta(days=1)
    month = barns.month_date(request.POST.get("month") or request.GET.get("month") or previous.isoformat())
    if request.method == "POST":
        try:
            if request.POST.get("verified") != "yes":
                raise ValidationError("Подтвердите проверку фактических остатков.")
            values = {str(p.pk): {"amount": request.POST.get(f"closing_{p.pk}"), "packages": request.POST.get(f"packs_{p.pk}", "")}
                for p in FeedProduct.objects.all() if f"closing_{p.pk}" in request.POST}
            barns.close_month(request.user, barn, month, values, request.POST.get("note"), request.POST.get("token"))
            messages.success(request, "Фактический расход за месяц подтверждён.")
            return redirect("feed_inventory:barn", barn=barn)
        except ValidationError as exc:
            views.error(request, exc)
    rows = barns.closing_rows(barn, month)
    period = BarnFeedPeriod.objects.filter(barn=barn, month=month).select_related("closing").first()
    estimate = None
    closed_rows = []
    if period and period.closing_id:
        closed_rows = map_closing.reconciliation_details(barn, month, barns.month_end(month))["rows"]
    elif barns.month_end(month) < timezone.localdate():
        estimate = barn_forecast.consumption_estimate(barn, month, barns.month_end(month), rows, period.plan if period else None)
    for row in rows:
        row["closing_value"] = request.POST.get(f"closing_{row['product'].pk}", "")
        row["packs_value"] = request.POST.get(f"packs_{row['product'].pk}", "0")
    return page(request, "close", barn=barn, month=month.isoformat()[:7], rows=rows,
        period=period, estimate=estimate, closed_rows=closed_rows,
        periods=BarnFeedPeriod.objects.filter(barn=barn).order_by("-month"), form=request.POST,
        token=request.POST.get("token") or uuid.uuid4())


@require_GET
@access
def analytics(request):
    if barns.can_supply(request.user):
        for i in range(1, 5):
            barns.ensure_period(i)
    return page(request, "analytics", comparison=barns.comparison(request.GET.get("month")), can_edit=can_manage_inventory(request.user))


@require_GET
@access
def attachment(request, pk):
    doc = get_object_or_404(BarnFeedDocument, pk=pk)
    if not doc.filename:
        raise Http404
    import hashlib
    if hashlib.sha256(bytes(doc.content)).hexdigest() != doc.sha256:
        raise ValidationError("Контрольная сумма не совпадает.")
    return FileResponse(BytesIO(bytes(doc.content)), as_attachment=True, filename=doc.filename, content_type=doc.content_type)
