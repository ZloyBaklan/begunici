import hashlib
import uuid
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Sum, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_GET
from io import BytesIO

from begunici.app_types.inventory.permissions import can_manage_inventory
from begunici.app_types.veterinary.vet_models import VeterinaryCare, Veterinary
from .permissions import access_required, can_treat
from . import services
from .models import VetDocument, VetMovement, VetOrder, VetProduct, VetVersion, VetNorm, VetTreatment
from . import rules, treatments


def page(request, template, **context):
    return render(request, f"vet_inventory/{template}.html", {
        "can_finance": can_manage_inventory(request.user), "can_treat": can_treat(request.user),
        "technical_care_tab": "norms" if template in {"norms", "norm_edit"} else "", **context})


def paginate_settings(request, queryset):
    from django.core.paginator import Paginator
    page_obj = Paginator(queryset, 10).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return {"page_obj": page_obj, "pagination_query": query.urlencode()}


def error(request, exc):
    request._stock_audit_error = "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Запись уже изменилась. Обновите страницу и проверьте данные."
    messages.error(request, request._stock_audit_error)


def posted_lines(request, products):
    if "line_product" in request.POST:
        columns = [request.POST.getlist(key) for key in ("line_product", "line_amount", "line_packages", "line_size")]
        if len({len(column) for column in columns}) != 1 or len(columns[0]) > 200:
            raise ValidationError("Проверьте строки номенклатуры.")
        allowed = {str(p.pk) for p in products}
        if any(pk not in allowed for pk in columns[0]):
            raise ValidationError("Номенклатура отсутствует в этой форме или заявке.")
        return [dict(product=p, amount=a, packages=n, package_size=s) for p, a, n, s in zip(*columns)]
    return [{"product": p.pk, "amount": request.POST.get(f"amount_{p.pk}", ""),
             "packages": request.POST.get(f"packages_{p.pk}", "")} for p in products]


def posted_group_expenses(request):
    if "expense_group" not in request.POST:
        return None
    columns = [request.POST.getlist(key) for key in ("expense_group", "expense_variant", "expense_quantity")]
    if len({len(column) for column in columns}) != 1 or len(columns[0]) > 200:
        raise ValidationError("Проверьте строки группового расхода.")
    return [dict(group=g, variant=v, amount=q) for g, v, q in zip(*columns)]


def group_editor(request, products, initial=None):
    groups = services.expense_groups(products)
    try:
        rows = posted_group_expenses(request) if request.method == "POST" else None
    except ValidationError:
        rows = None
    rows = rows if rows is not None else initial or [{}]
    references = {variant["id"]: group["id"] for group in groups for variant in group["variants"]}
    return {"expense_groups": groups, "group_expense_rows": [
        {**row, "group": references.get(str(row.get("group")), str(row.get("group") or ""))} for row in rows]}


def physical_editor(request, products, initial=None, single=False, weight_requirements=None):
    groups = services.product_groups(products)
    if weight_requirements is not None:
        for group in groups:
            for variant in group["variants"]:
                variant["requires_weight"] = bool(weight_requirements.get(variant["id"], False))
    references = {variant["id"]: group["id"] for group in groups for variant in group["variants"]}
    if request.method == "POST" and single:
        rows = [{"product": request.POST.get("product"), "amount": request.POST.get("quantity", "")}]
    elif request.method == "POST" and "line_product" in request.POST:
        rows = [{"product": pk, "amount": qty} for pk, qty in zip(request.POST.getlist("line_product"), request.POST.getlist("line_amount"))]
    else:
        rows = initial or [{}]
    return {"physical_groups": groups, "physical_rows": [{**row, "product": str(row.get("product") or ""),
        "group": references.get(str(row.get("product")), "")} for row in rows], "single_expense": single,
        "weight_required": any((weight_requirements or {}).get(str(row.get("product")), False) for row in rows)}


def editor_rows(request, products, initial=None, show_available=False):
    from collections import defaultdict
    values = defaultdict(list)
    try:
        raw = posted_lines(request, products) if request.method == "POST" and (
            "line_product" in request.POST or any(f"amount_{p.pk}" in request.POST for p in products)) else initial or []
    except ValidationError:
        raw = initial or []
    for row in raw:
        values[int(row["product"])].append(row)
    stock = services.balances() if show_available else {}
    rows = []
    for product in products:
        for row in values.get(product.pk, [{}]):
            rows.append({"product": product,
                     "available": stock.get(product.pk, (Decimal(0), Decimal(0)))[0],
                     "amount": row.get("amount", ""), "packages": row.get("packages", ""),
                     "package_size": row.get("package_size", services.number(product.package_size) if product.package_size and not row else "")})
    return rows


def posted_product_details(request, product=None):
    return {key: request.POST[key] if key in request.POST else getattr(product, key, None)
            for key in ("package_size", "concentration", "concentration_unit")}


def product_form_options(product=None):
    units = list(services.CATALOG_UNITS)
    concentrations = list(services.CATALOG_CONCENTRATIONS)
    # Keep unsupported legacy values selectable only on their existing card.
    for field, choices in (("unit", units), ("concentration_unit", concentrations)):
        value = getattr(product, field, "")
        if value and value not in dict(choices):
            label = dict(VetProduct._meta.get_field(field).choices)[value]
            choices.append((value, label + " (сохранённое значение)"))
    return {"units": units, "concentrations": concentrations,
            "categories": VetProduct._meta.get_field("category").choices}


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
    return page(request, "home", stock=stock, stock_groups=services.group_stock_rows(stock), pending=VetTreatment.objects.filter(state="pending").count(),
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
@access_required(write=True)
def document_new(request, kind, order_id=None):
    if kind not in {"receipt", "consume", "writeoff"}:
        raise Http404
    order = get_object_or_404(VetOrder, pk=order_id) if kind == "receipt" else None
    products = list(VetProduct.objects.filter(pk__in=[r["product"] for r in order.lines]) if order else VetProduct.objects.all())
    initial = ([{"product": r["product"], "amount": str(r["missing"]), "packages": str(r["missing_packages"])}
                for r in services.order_progress(order)["rows"]] if order else [])
    if order:
        for row, original in zip(initial, order.lines):
            row["package_size"] = original.get("package_size", "")
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
                **(physical_editor(request, products) if kind != "receipt" else {}),
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
                **(physical_editor(request, products, version.payload["lines"])
                   if document.kind in {"consume", "writeoff"} else {}),
                reasons=services.WRITEOFF_REASONS, show_available=document.kind == "writeoff",
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
    content = bytes(version.content)
    if hashlib.sha256(content).hexdigest() != version.sha256:
        return HttpResponse("Контрольная сумма документа не совпадает. Файл не выдан.", status=409)
    response = FileResponse(BytesIO(content), as_attachment=True, filename=version.filename,
                            content_type=version.content_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@require_http_methods(["GET", "POST"])
@access_required()
def products(request):
    if request.method == "POST":
        try:
            services.create_product(request.user, request.POST.get("name"), request.POST.get("category"),
                                    request.POST.get("unit"), automatic_name=True, **posted_product_details(request))
            messages.success(request, "Препарат добавлен. Свяжите его с обработкой в разделе норм расхода.")
            request._inventory_logged = True
            return redirect("inventory_catalog:vet-products")
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    groups = {}
    for product in VetProduct.objects.order_by("pk"):
        name = services.common_product_name(product)
        group = groups.setdefault((name.casefold(), product.category), {"name": name, "products": []})
        group["products"].append(product)
    number = 1
    for group in groups.values():
        for product in group["products"]:
            product.catalog_number = number
            number += 1
    pagination = paginate_settings(request, list(groups.values()))
    product_groups = list(pagination["page_obj"])
    return page(request, "products", product_groups=product_groups,
                products=[product for group in product_groups for product in group["products"]],
                pagination_unit="групп", form=request.POST, **pagination,
                **product_form_options())


@require_http_methods(["GET", "POST"])
@access_required()
def product_edit(request, pk):
    product = get_object_or_404(VetProduct, pk=pk)
    if request.method == "POST":
        try:
            services.update_product(request.user, pk, request.POST.get("revision"), request.POST.get("name"),
                request.POST.get("category"), request.POST.get("unit"),
                automatic_name=True, **posted_product_details(request, product))
            messages.success(request, "Номенклатура изменена. Ранее оформленные документы сохранены без изменений.")
            request._inventory_logged = True
            return redirect("inventory_catalog:vet-products")
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    values = request.POST if request.method == "POST" else {
        "name": product.base_name or product.name, "category": product.category, "unit": product.unit,
        "revision": product.revision,
        "package_size": services.number(product.package_size) if product.package_size else "",
        "concentration": services.number(product.concentration) if product.concentration else "",
        "concentration_unit": product.concentration_unit,
    }
    restrictions = services.product_restrictions(product)
    restrictions["size_locked"] = bool(product.base_name and restrictions["size_locked"])
    return page(request, "product_edit", product=product, form=values,
                **restrictions, **product_form_options(product))


@require_http_methods(["GET", "POST"])
@access_required()
def norm_edit(request, pk):
    care = get_object_or_404(VeterinaryCare, pk=pk)
    if rules.is_shearing(care):
        messages.info(request, treatments.SHEARING_NO_EXPENSE)
        return redirect(reverse("veterinary:veterinary_cares") + "?tab=norms")
    products = list(VetProduct.objects.all())
    groups = services.product_groups(products)
    existing = {str(rule.product_id): rule for rule in VetNorm.objects.filter(care=care).select_related("product")}
    references = {variant["id"]: group["id"] for group in groups for variant in group["variants"]}
    group_id = request.POST.get("norm_group", "") if request.method == "POST" else request.GET.get(
        "group", references.get(next(iter(existing), ""), ""))
    group = next((group for group in groups if group["id"] == group_id), None)
    posted, conditions = [], []
    if request.method == "POST":
        try:
            keys = ("product", "revision", "unit", "mode", "rate", "weight_step")
            columns = [request.POST.getlist("norm_" + key) for key in keys]
            if len({len(column) for column in columns}) != 1 or len(columns[0]) > 200:
                raise ValidationError("Проверьте строки норм препаратов.")
            posted = [dict(zip(keys, values)) for values in zip(*columns)]
            keys = ("product", "age_from", "age_to", "weight_from", "weight_to", "rate")
            columns = [request.POST.getlist("condition_" + key) for key in keys]
            if len({len(column) for column in columns}) != 1 or len(columns[0]) > 200:
                raise ValidationError("Проверьте заполнение всех колонок условий.")
            conditions = [dict(zip(keys, values)) for values in zip(*columns) if any(str(v).strip() for v in values)]
            rules.save_product_rules(request.user, pk, group_id, posted, conditions)
            messages.success(request, "Нормы препаратов сохранены. Ранее учтённый расход не изменён.")
            request._inventory_logged = True
            return redirect(reverse("veterinary:veterinary_cares") + "?tab=norms")
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    posted = {str(row["product"]): row for row in posted}
    by_id = {str(product.pk): product for product in products}
    rows = []
    for variant in group["variants"] if group else []:
        product = by_id[variant["id"]]
        rule = existing.get(variant["id"])
        direct = rules.direct_rule(rule)
        values = posted.get(variant["id"], {})
        rows.append({"product": product, "revision": values.get("revision", rule.revision if rule else 0),
            "mode": values.get("mode", rule.mode if direct else "head"),
            "rate": values.get("rate", services.number(rule.rate) if direct and rule.rate is not None else ""),
            "weight_step": values.get("weight_step", services.number(rule.weight_step) if direct and rule.weight_step else ""),
            "unit": values.get("unit", (rule.dose_unit or product.unit) if direct else product.unit),
            "unit_label": dict(rules.DOSE_UNITS).get(values.get("unit", (rule.dose_unit or product.unit) if direct else product.unit)),
            "legacy": bool(rule and not direct)})
        variant["norm_unit"] = rows[-1]["unit_label"]
        if request.method == "GET" and direct:
            entries = rule.conditions or ([{"weight_from": b["from"], "weight_to": b["to"], "rate": b["amount"]}
                for b in rule.bands] if rule.mode == "bands" else [])
            conditions.extend({**condition, "product": variant["id"]} for condition in entries)
    return page(request, "norm_edit", care=care, products=products, norm_groups=groups, selected_group=group,
        norm_rows=rows, condition_rows=conditions or [{}],
        modes=VetNorm._meta.get_field("mode").choices)

@require_GET
@access_required()
def norms(request):
    pagination = paginate_settings(request, VeterinaryCare.objects.order_by("care_type", "care_name", "pk"))
    cares = list(pagination["page_obj"].object_list)
    mapping = {}
    for rule in VetNorm.objects.filter(care_id__in=[c.pk for c in cares]).select_related("product").order_by("product_id"):
        mapping.setdefault(rule.care_id, []).append({"rule": rule, "details": rules.rule_data(rule), "direct": rules.direct_rule(rule)})
    return page(request, "norms", entries=[{"care": c, "rule": mapping[c.pk][0]["rule"] if c.pk in mapping else None,
        "product_rules": mapping.get(c.pk, []),
        "requires_stock": not rules.is_shearing(c)} for c in cares], **pagination)


@require_GET
@access_required()
def treatment_list(request):
    entries = VetTreatment.objects.select_related("product", "document")
    query = request.GET.get("q", "").strip()
    state = request.GET.get("state", "")
    tag = request.GET.get("tag", "")
    if state in dict(VetTreatment._meta.get_field("state").choices):
        entries = entries.filter(state=state)
    if tag.isdigit():
        entries = entries.filter(snapshot__tag_id=int(tag))
    if query:
        entries = entries.filter(Q(snapshot__tag__icontains=query) | Q(snapshot__care__icontains=query)
                                 | Q(product__name__icontains=query) | Q(calculation__group_expenses__0__name__icontains=query))
    pagination = paginate_settings(request, entries)
    return page(request, "treatments", entries=pagination["page_obj"], query=query, state=state, tag=tag, **pagination)


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
                    request.POST.get("quantity"), request.POST.get("reason"), recalculate=action == "recalculate",
                    weight=request.POST.get("weight"), direct=True)
            else:
                raise ValidationError("Неизвестное действие.")
            return redirect("vet_inventory:treatment", pk=pk)
        except (ValidationError, IntegrityError) as exc:
            error(request, exc)
    values = request.POST if request.method == "POST" else {"product": str(entry.product_id or ""),
        "quantity": services.number(entry.quantity) if entry.quantity is not None else "", "revision": entry.revision,
        "weight": entry.calculation.get("weight", "")}
    documents = VetDocument.objects.filter(versions__payload__treatment_id=pk).distinct().order_by("-pk")
    products = list(VetProduct.objects.all())
    initial = [{"product": entry.product_id, "amount": services.number(entry.quantity) if entry.quantity is not None else ""}]
    source = Veterinary.objects.filter(pk=entry.source_id).only("veterinary_care_id").first()
    weight_requirements = {str(rule.product_id): bool(rules.requires_weight(rule)) for rule in
        VetNorm.objects.filter(care_id=source.veterinary_care_id, auto_variant=False, dose_basis="product")} if source else {}
    return page(request, "treatment", entry=entry, form=values, products=VetProduct.objects.all(), documents=documents,
        **physical_editor(request, products, initial, single=True, weight_requirements=weight_requirements),
        requires_stock=treatments.requires_stock(entry),
        weight_required_issue=rules.WEIGHT_REQUIRED_MESSAGE,
        source_exists=source is not None)


@require_GET
@access_required()
def treatment_estimate(request, pk):
    entry = get_object_or_404(VetTreatment, pk=pk)
    source = Veterinary.objects.select_related("tag", "veterinary_care").filter(pk=entry.source_id).first()
    if source is None or entry.state == "deleted":
        return JsonResponse({"error": "Исходная обработка недоступна для расчёта."}, status=400)
    if not request.GET.get("product"):
        return JsonResponse({"error": "Выберите конкретный препарат."}, status=400)
    try:
        product, quantity, calculation = rules.estimate_product(source, request.GET.get("product"), request.GET.get("weight"))
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages),
            "requires_weight": any(error.code == "weight_required" for error in exc.error_list)}, status=400)
    return JsonResponse({"quantity": services.number(quantity), "unit": product.get_unit_display(),
        "mode": calculation["mode_label"], "requires_weight": calculation["requires_weight"]})
