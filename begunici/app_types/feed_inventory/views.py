import uuid
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_GET
from io import BytesIO

from begunici.app_types.inventory.permissions import access_required
from . import services
from .models import FeedAudit, FeedDocument, FeedMovement, FeedOrder, FeedProduct, FeedVersion
from .plan import build_plan, feed_plan_response


def page(request, template, **context):
    return render(request, f"feed_inventory/{template}.html", {"section": "feeds", **context})


def error(request, exc):
    messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError)
                   else "Запись уже изменилась. Обновите страницу и проверьте данные.")


def posted_lines(request, products):
    return [{"product": p.pk, "amount": request.POST.get(f"amount_{p.pk}", ""),
             "packages": request.POST.get(f"packages_{p.pk}", "")} for p in products]


def editor_rows(request, products, initial=None, show_available=False):
    initial = {int(row["product"]): row for row in initial or []}
    stock = services.balances() if show_available else {}
    rows = []
    for product in products:
        row = initial.get(product.pk, {})
        rows.append({"product": product,
                     "available": stock.get(product.pk, (Decimal(0), Decimal(0)))[0],
                     "amount": request.POST.get(f"amount_{product.pk}", row.get("amount", "")),
                     "packages": request.POST.get(f"packages_{product.pk}", row.get("packages", ""))})
    return rows


@require_GET
@access_required()
def home(request):
    plan = build_plan()
    today = timezone.localdate()
    actual = {row["product_id"]: -row["amount"] for row in
              FeedMovement.objects.filter(document__kind="consume", document__state="posted", document__date=today)
              .values("product_id").annotate(amount=Sum("amount"))}
    stock = services.stock_rows(plan)
    written_off = {row["product_id"]: -row["amount"] for row in
                   FeedMovement.objects.filter(document__kind="writeoff", document__state="posted", document__date=today)
                   .values("product_id").annotate(amount=Sum("amount"))}
    for row in stock:
        row["actual"] = actual.get(row["id"], Decimal(0))
        row["written_off"] = written_off.get(row["id"], Decimal(0))
    return page(request, "home", stock=stock, plan=plan,
                consumption_confirmed=FeedDocument.objects.filter(kind="consume", state="posted", date=today).exists(),
                documents=FeedDocument.objects.select_related("created_by", "order")[:30])


@require_http_methods(["GET", "POST"])
@access_required()
def orders(request):
    products = list(FeedProduct.objects.all())
    if request.method == "POST":
        try:
            order = services.create_order(request.user, request.POST.get("supplier"), request.POST.get("note"),
                                          posted_lines(request, products), request.POST.get("token"))
            return redirect("feed_inventory:order", pk=order.pk)
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    entries = [{"order": order, "progress": services.order_progress(order)} for order in FeedOrder.objects.order_by("-pk")]
    return page(request, "orders", orders=entries, rows=editor_rows(request, products),
                form=request.POST, token=request.POST.get("token") or uuid.uuid4())


@require_GET
@access_required()
def order_detail(request, pk):
    order = get_object_or_404(FeedOrder, pk=pk)
    return page(request, "order", order=order, progress=services.order_progress(order), documents=order.feeddocument_set.all())


@require_http_methods(["GET", "POST"])
@access_required()
def document_new(request, kind, order_id=None):
    if kind not in {"receipt", "consume", "writeoff"}:
        raise Http404
    order = get_object_or_404(FeedOrder, pk=order_id) if kind == "receipt" else None
    plan = build_plan()
    products = list(FeedProduct.objects.filter(pk__in=[r["product"] for r in order.lines]) if order else FeedProduct.objects.all())
    initial = ([{"product": r["product"], "amount": str(r["missing"]), "packages": str(r["missing_packages"])}
                for r in services.order_progress(order)["rows"]] if order else
               [{"product": p["id"], "amount": p["daily"], "packages": "0"} for p in plan["products"]])
    if kind == "writeoff":
        initial = []
    if request.method == "POST":
        try:
            document = services.create_document(request.user, kind, request.POST.get("date"), request.POST.get("number"),
                posted_lines(request, products), request.POST.get("note"), request.POST.get("token"),
                order_id=order_id, upload=request.FILES.get("file"), reason=request.POST.get("reason"))
            return redirect("feed_inventory:document", pk=document.pk)
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    return page(request, "document_form", kind=kind, order=order, plan=plan, form=request.POST,
                reasons=services.WRITEOFF_REASONS, show_available=kind == "writeoff",
                date=request.POST.get("date", timezone.localdate().isoformat()),
                token=request.POST.get("token") or uuid.uuid4(), rows=editor_rows(request, products, initial, kind == "writeoff"))


@require_http_methods(["GET", "POST"])
@access_required()
def document_detail(request, pk):
    document = get_object_or_404(FeedDocument.objects.select_related("order", "created_by", "posted_by", "reversal_of"), pk=pk)
    version = document.versions.first()
    products = list(FeedProduct.objects.filter(pk__in=[r["product"] for r in document.order.lines]) if document.order_id else FeedProduct.objects.all())
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "confirm":
                if request.POST.get("verified") != "yes":
                    raise ValidationError("Подтвердите проверку номенклатуры и количеств.")
                services.confirm_document(request.user, pk, request.POST.get("revision"))
            elif action == "edit":
                services.edit_draft(request.user, pk, request.POST.get("revision"), posted_lines(request, products),
                    request.POST.get("note"), request.FILES.get("file"), request.POST.get("replace") == "yes", request.POST.get("reason"))
            elif action == "cancel":
                services.cancel_draft(request.user, pk, request.POST.get("revision"))
            elif action == "reverse":
                reversal = services.reverse_document(request.user, pk, request.POST.get("reason"))
                return redirect("feed_inventory:document", pk=reversal.pk)
            else:
                raise ValidationError("Неизвестное действие.")
            return redirect("feed_inventory:document", pk=pk)
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    return page(request, "document", document=document, version=version,
                reasons=services.WRITEOFF_REASONS, show_available=document.kind == "writeoff",
                versions=document.versions.select_related("created_by"),
                form=request.POST, editing=request.POST.get("action") == "edit",
                rows=editor_rows(request, products, version.payload["lines"], document.kind == "writeoff"))


@require_GET
@access_required()
def writeoffs(request):
    from django.core.paginator import Paginator
    documents = FeedDocument.objects.filter(kind="writeoff").select_related("created_by")
    entries = Paginator(documents, 30).get_page(request.GET.get("page"))
    return page(request, "writeoffs", documents=entries)


@require_GET
@access_required()
def writeoff_print(request, pk):
    version = get_object_or_404(FeedVersion.objects.select_related("document", "created_by"), pk=pk, document__kind="writeoff")
    return render(request, "feed_inventory/writeoff_print.html", {"version": version, "document": version.document})


@require_GET
@access_required()
def version_download(request, pk):
    version = get_object_or_404(FeedVersion, pk=pk)
    if not version.filename:
        raise Http404
    return FileResponse(BytesIO(bytes(version.content)), as_attachment=True, filename=version.filename,
                        content_type=version.content_type)


@require_http_methods(["GET", "POST"])
@access_required()
def products(request):
    if request.method == "POST":
        try:
            services.create_product(request.user, request.POST.get("name"), request.POST.get("category"),
                                    request.POST.get("unit"), request.POST.get("package"))
            messages.success(request, "Номенклатура добавлена. Нормы можно задать в кормовом плане на главной.")
            return redirect("feed_inventory:products")
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    return page(request, "products", products=FeedProduct.objects.all(), form=request.POST,
                categories=FeedProduct._meta.get_field("category").choices, units=FeedProduct._meta.get_field("unit").choices)


@require_http_methods(["GET", "POST"])
@access_required()
def product_edit(request, pk):
    product = get_object_or_404(FeedProduct, pk=pk)
    if request.method == "POST":
        try:
            services.update_product(request.user, pk, request.POST.get("revision"), request.POST.get("name"),
                request.POST.get("category"), request.POST.get("unit"), request.POST.get("package"))
            messages.success(request, "Номенклатура изменена. Ранее оформленные документы сохранены без изменений.")
            return redirect("feed_inventory:products")
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    values = request.POST if request.method == "POST" else {
        "name": product.name, "category": product.category, "unit": product.unit,
        "package": product.package, "revision": product.revision,
    }
    return page(request, "product_edit", product=product, form=values,
                **services.product_restrictions(product),
                categories=FeedProduct._meta.get_field("category").choices, units=FeedProduct._meta.get_field("unit").choices)


@require_http_methods(["POST"])
@access_required()
def norms(request):
    try:
        services.save_norms(request.user, request.POST.get("revision"), request.POST)
        messages.success(request, "Нормы сохранены. Кормовой план и Excel пересчитаны.")
        return redirect("/#feed-plan")
    except (ValidationError, IntegrityError) as exc:
        error(request, exc)
    plan = build_plan()
    for row in plan["rows"]:
        for cell in row["cells"]:
            cell["norm"] = request.POST.get(f"norm_{cell['product_id']}_{row['group']}", cell["norm"])
    # Keep the submitted revision: a stale form must not overwrite another edit.
    plan["revision"] = request.POST.get("revision", "")
    return page(request, "norms", plan=plan, can_edit=True, editing=True)


@require_GET
@login_required
def export(request):
    period = "yearly" if request.GET.get("period") == "yearly" else "monthly"
    return feed_plan_response(period=period)


@require_GET
@access_required()
def history(request):
    from django.core.paginator import Paginator
    events = FeedAudit.objects.select_related("created_by").order_by("-pk")
    return page(request, "history", events=Paginator(events, 50).get_page(request.GET.get("page")))
