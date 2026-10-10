import uuid
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Sum, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_GET
from io import BytesIO

from begunici.app_types.inventory.permissions import can_manage_inventory
from begunici.app_types.veterinary.vet_models import VeterinaryCare, Veterinary
from .permissions import access_required, can_treat
from . import services
from .models import VetAudit, VetDocument, VetMovement, VetOrder, VetProduct, VetVersion, VetNorm, VetTreatment
from . import rules, treatments


def page(request, template, **context):
    return render(request, f"vet_inventory/{template}.html", {
        "can_finance": can_manage_inventory(request.user), "can_treat": can_treat(request.user), **context})


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
    today = timezone.localdate()
    actual = {row["product_id"]: -row["amount"] for row in
              VetMovement.objects.filter(document__kind__in=["consume", "treatment"], document__state="posted", document__date=today)
              .values("product_id").annotate(amount=Sum("amount"))}
    stock = services.stock_rows()
    written_off = {row["product_id"]: -row["amount"] for row in
                   VetMovement.objects.filter(document__kind="writeoff", document__state="posted", document__date=today)
                   .values("product_id").annotate(amount=Sum("amount"))}
    for row in stock:
        row["actual"] = actual.get(row["id"], Decimal(0))
        row["written_off"] = written_off.get(row["id"], Decimal(0))
    return page(request, "home", stock=stock, pending=VetTreatment.objects.filter(state="pending").count(),
                documents=VetDocument.objects.select_related("created_by", "order")[:30])


@require_http_methods(["GET", "POST"])
@access_required()
def orders(request):
    products = list(VetProduct.objects.all())
    if request.method == "POST":
        try:
            order = services.create_order(request.user, request.POST.get("supplier"), request.POST.get("note"),
                                          posted_lines(request, products), request.POST.get("token"))
            return redirect("vet_inventory:order", pk=order.pk)
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    entries = [{"order": order, "progress": services.order_progress(order)} for order in VetOrder.objects.order_by("-pk")]
    return page(request, "orders", orders=entries, rows=editor_rows(request, products),
                form=request.POST, token=request.POST.get("token") or uuid.uuid4())


@require_GET
@access_required()
def order_detail(request, pk):
    order = get_object_or_404(VetOrder, pk=pk)
    return page(request, "order", order=order, progress=services.order_progress(order), documents=order.vetdocument_set.all())


@require_http_methods(["GET", "POST"])
@access_required()
def document_new(request, kind, order_id=None):
    if kind not in {"receipt", "consume", "writeoff"}:
        raise Http404
    order = get_object_or_404(VetOrder, pk=order_id) if kind == "receipt" else None
    products = list(VetProduct.objects.filter(pk__in=[r["product"] for r in order.lines]) if order else VetProduct.objects.all())
    initial = ([{"product": r["product"], "amount": str(r["missing"]), "packages": str(r["missing_packages"])}
                for r in services.order_progress(order)["rows"]] if order else [])
    if kind == "writeoff":
        initial = []
    if request.method == "POST":
        try:
            document = services.create_document(request.user, kind, request.POST.get("date"), request.POST.get("number"),
                posted_lines(request, products), request.POST.get("note"), request.POST.get("token"),
                order_id=order_id, upload=request.FILES.get("file"), reason=request.POST.get("reason"))
            return redirect("vet_inventory:document", pk=document.pk)
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    return page(request, "document_form", kind=kind, order=order, form=request.POST,
                reasons=services.WRITEOFF_REASONS, show_available=kind == "writeoff",
                date=request.POST.get("date", timezone.localdate().isoformat()),
                token=request.POST.get("token") or uuid.uuid4(), rows=editor_rows(request, products, initial, kind == "writeoff"))


@require_http_methods(["GET", "POST"])
@access_required()
def document_detail(request, pk):
    document = get_object_or_404(VetDocument.objects.select_related("order", "created_by", "posted_by", "reversal_of"), pk=pk)
    version = document.versions.first()
    products = list(VetProduct.objects.filter(pk__in=[r["product"] for r in document.order.lines]) if document.order_id else VetProduct.objects.all())
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
                return redirect("vet_inventory:document", pk=reversal.pk)
            else:
                raise ValidationError("Неизвестное действие.")
            return redirect("vet_inventory:document", pk=pk)
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
    documents = VetDocument.objects.filter(kind="writeoff").select_related("created_by")
    entries = Paginator(documents, 30).get_page(request.GET.get("page"))
    return page(request, "writeoffs", documents=entries)


@require_GET
@access_required()
def writeoff_print(request, pk):
    version = get_object_or_404(VetVersion.objects.select_related("document", "created_by"), pk=pk, document__kind="writeoff")
    return render(request, "vet_inventory/writeoff_print.html", {"version": version, "document": version.document})


@require_GET
@access_required()
def version_download(request, pk):
    version = get_object_or_404(VetVersion, pk=pk)
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
            messages.success(request, "Препарат добавлен. Свяжите его с обработкой в разделе норм расхода.")
            return redirect("vet_inventory:products")
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    return page(request, "products", products=VetProduct.objects.all(), form=request.POST,
                categories=VetProduct._meta.get_field("category").choices, units=VetProduct._meta.get_field("unit").choices)


@require_http_methods(["GET", "POST"])
@access_required()
def product_edit(request, pk):
    product = get_object_or_404(VetProduct, pk=pk)
    if request.method == "POST":
        try:
            services.update_product(request.user, pk, request.POST.get("revision"), request.POST.get("name"),
                request.POST.get("category"), request.POST.get("unit"), request.POST.get("package"))
            messages.success(request, "Номенклатура изменена. Ранее оформленные документы сохранены без изменений.")
            return redirect("vet_inventory:products")
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    values = request.POST if request.method == "POST" else {
        "name": product.name, "category": product.category, "unit": product.unit,
        "package": product.package, "revision": product.revision,
    }
    return page(request, "product_edit", product=product, form=values,
                **services.product_restrictions(product),
                categories=VetProduct._meta.get_field("category").choices, units=VetProduct._meta.get_field("unit").choices)


@require_http_methods(["GET", "POST"])
@access_required()
def norm_edit(request, pk):
    care = get_object_or_404(VeterinaryCare, pk=pk)
    rule = VetNorm.objects.filter(care=care).first()
    bands = [{"from": a, "to": b, "amount": c} for a, b, c in zip(
        request.POST.getlist("band_from"), request.POST.getlist("band_to"), request.POST.getlist("band_amount"))
        if a.strip() or b.strip() or c.strip()] if request.method == "POST" else (rule.bands if rule else [])
    if request.method == "POST":
        try:
            rules.save_rule(request.user, pk, request.POST.get("revision"), request.POST.get("product"),
                request.POST.get("mode"), request.POST.get("rate"), bands)
            messages.success(request, "Норма сохранена. Она применяется к новым обработкам; ранее учтённый расход сохранён.")
            return redirect("vet_inventory:norms")
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    values = request.POST if request.method == "POST" else {
        "product": str(rule.product_id) if rule else "", "mode": rule.mode if rule else "head",
        "rate": services.number(rule.rate) if rule and rule.rate is not None else "", "revision": rule.revision if rule else 0}
    return page(request, "norm_edit", care=care, rule=rule, form=values, products=VetProduct.objects.all(),
                bands=bands or [{"from": "0", "to": "", "amount": ""}])


@require_GET
@access_required()
def norms(request):
    mapping = {r.care_id: r for r in VetNorm.objects.select_related("product")}
    return page(request, "norms", entries=[{"care": c, "rule": mapping.get(c.pk)} for c in VeterinaryCare.objects.order_by("care_type", "care_name", "pk")])


@require_GET
@access_required()
def treatment_list(request):
    from django.core.paginator import Paginator
    entries = VetTreatment.objects.select_related("product", "document")
    query = request.GET.get("q", "").strip()
    state = request.GET.get("state", "")
    tag = request.GET.get("tag", "")
    if state in dict(VetTreatment._meta.get_field("state").choices):
        entries = entries.filter(state=state)
    if tag.isdigit():
        entries = entries.filter(snapshot__tag_id=int(tag))
    if query:
        entries = entries.filter(Q(snapshot__tag__icontains=query) | Q(snapshot__care__icontains=query) | Q(product__name__icontains=query))
    return page(request, "treatments", entries=Paginator(entries, 50).get_page(request.GET.get("page")), query=query, state=state, tag=tag)


@require_http_methods(["GET", "POST"])
@access_required()
def treatment_detail(request, pk):
    entry = get_object_or_404(VetTreatment.objects.select_related("product", "document"), pk=pk)
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "exclude":
                treatments.exclude(request.user, pk, request.POST.get("revision"), request.POST.get("reason"))
            elif action in {"adjust", "recalculate"}:
                treatments.adjust(request.user, pk, request.POST.get("revision"), request.POST.get("product"),
                    request.POST.get("quantity"), request.POST.get("reason"), recalculate=action == "recalculate")
            else:
                raise ValidationError("Неизвестное действие.")
            return redirect("vet_inventory:treatment", pk=pk)
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    values = request.POST if request.method == "POST" else {"product": str(entry.product_id or ""),
        "quantity": services.number(entry.quantity) if entry.quantity is not None else "", "revision": entry.revision}
    documents = VetDocument.objects.filter(versions__payload__treatment_id=pk).distinct().order_by("-pk")
    return page(request, "treatment", entry=entry, form=values, products=VetProduct.objects.all(), documents=documents,
        source_exists=Veterinary.objects.filter(pk=entry.source_id).exists(),
        events=VetAudit.objects.filter(data__treatment=pk).select_related("created_by").order_by("-pk"))


@require_GET
@access_required()
def history(request):
    from django.core.paginator import Paginator
    events = VetAudit.objects.select_related("created_by").order_by("-pk")
    return page(request, "history", events=Paginator(events, 50).get_page(request.GET.get("page")))
