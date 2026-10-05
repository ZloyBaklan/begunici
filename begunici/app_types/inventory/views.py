import hashlib
import json
from functools import wraps
from urllib.parse import quote

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import bridges, invoices, orders, receipts, stock
from .animal_types import ANIMAL_TYPE_CHOICES
from .documents import add_version, assert_editable, assert_revision
from .models import AnimalCase, AuditEvent, Document, DocumentVersion, Order, Product, StockLot, StockMovement
from .permissions import access_required, can_manage_inventory, can_prepare_slaughter, require_inventory
from .presentation import animal_display
from .selectors import archive_rows, pending_animals, stock_summary


def api(view):
    @wraps(view)
    @require_POST
    def wrapped(request, *args, **kwargs):
        try:
            data = json.loads(request.POST.get("data", "{}")) if request.content_type and request.content_type.startswith("multipart/") else json.loads(request.body or b"{}")
            if not isinstance(data, dict):
                raise ValidationError("Ожидается объект запроса.")
            return JsonResponse(view(request, data, *args, **kwargs))
        except invoices.IncompleteOrder as exc:
            return JsonResponse({"error": " ".join(exc.messages), "needs_keep_open": True, "report": exc.report}, status=409)
        except PermissionDenied:
            return JsonResponse({"error": "Нет доступа к этому действию."}, status=403)
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            message = " ".join(exc.messages) if isinstance(exc, ValidationError) else "Некорректный формат запроса. Обновите страницу и проверьте поля."
            return JsonResponse({"error": message}, status=400)
        except ObjectDoesNotExist:
            return JsonResponse({"error": "Запись не найдена. Обновите страницу."}, status=404)
        except IntegrityError:
            return JsonResponse({"error": "Запись уже изменена или создана другим сотрудником. Обновите страницу."}, status=409)
    return wrapped


def document_result(document):
    return {"id": document.pk, "url": reverse("inventory:document", args=[document.pk])}


def document_access(user, document):
    if document.kind == "sp55":
        if not (can_prepare_slaughter(user) or can_manage_inventory(user)):
            raise PermissionDenied
    else:
        require_inventory(user)


@require_GET
@access_required()
def dashboard(request, section="home"):
    context = {"section": section}
    if section == "live":
        context["animals"] = bridges.discover("live")
    elif section == "pending":
        context["animals"] = pending_animals()
    elif section == "stock":
        lots = list(stock.available_lots())
        context.update(lots=lots, summary=stock_summary(lots), invoices=Document.objects.filter(kind="invoice")[:100])
    elif section == "archive":
        context["archive"] = archive_rows()
    context["prepare_slaughter"] = can_prepare_slaughter(request.user)
    return render(request, "inventory/dashboard.html", context)


@require_GET
@access_required(slaughter=True)
def slaughter(request):
    return render(request, "inventory/slaughter.html", {
        "animals": pending_animals(meat_only=True), "documents": Document.objects.filter(kind="sp55"),
        "drafts": Document.objects.filter(kind="sp55", state__in=["draft", "ready"]),
        "prepare_slaughter": can_prepare_slaughter(request.user),
    })


@require_GET
@access_required()
def animal(request, tag_id):
    case = AnimalCase.objects.filter(source_tag_id=tag_id).select_related("receipt").first()
    try:
        source = bridges.source_info(bridges.source_animal(tag_id))
    except ValidationError as exc:
        if not case:
            raise Http404("Животное не найдено") from exc
        source = {"tag_id": tag_id, "tag_number": case.tag_number, "snapshot": case.snapshot,
                  "archive_date": case.archive_date, "status": case.snapshot.get("status", ""),
                  "for_sale": True, "is_archived": True, "unavailable": True}
    lots = list(stock.available_lots().filter(animal=case)) if case else []
    return render(request, "inventory/animal.html", {
        "animal": source, "case": case,
        "snapshot_display": animal_display(case.snapshot if case else source["snapshot"], case),
        "current_display": animal_display(source["snapshot"], case),
        "lots": lots, "invoice_lots": ",".join(str(lot.pk) for lot in lots),
        "invoices": Document.objects.filter(kind="invoice", movements__lot__animal=case).distinct() if case else [],
        "prepare_slaughter": can_prepare_slaughter(request.user),
        "eligible": not source.get("unavailable") and bridges.eligible(source) and source["archive_date"] and source["archive_date"] >= bridges.start_date(),
    })


@require_GET
def document(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    document_access(request.user, doc)
    context = {
        "document": doc, "animals": list(doc.animals.all()),
        "products": list(Product.objects.values("code", "name", "category", "counted")),
        "payload": doc.payload, "versions": doc.versions.defer("content").select_related("created_by"),
        "events": doc.events.select_related("actor"),
        "can_confirm": can_manage_inventory(request.user),
        "can_edit": can_prepare_slaughter(request.user) if doc.kind == "sp55" else can_manage_inventory(request.user),
    }
    if doc.kind == "invoice":
        context.update(invoice_context(order_id=doc.order_id))
    if can_manage_inventory(request.user):
        context["invoice_lots"] = ",".join(str(lot.pk) for lot in stock.available_lots().filter(animal__receipt=doc))
        context["deliveries"] = Document.objects.filter(kind="invoice", movements__lot__animal__receipt=doc).distinct()
        context["ledger"] = StockMovement.objects.filter(
            **({"document": doc} if doc.kind == "invoice" else {"lot__animal__receipt": doc})
        ).select_related("lot__animal", "lot__product", "created_by", "document").order_by("created_at", "id")
    return render(request, "inventory/document.html", context)


@require_GET
def version_download(request, pk, number):
    version = get_object_or_404(DocumentVersion.objects.select_related("document"), document_id=pk, number=number)
    document_access(request.user, version.document)
    content = bytes(version.content)
    if hashlib.sha256(content).hexdigest() != version.sha256:
        return HttpResponse("Контрольная сумма документа не совпадает. Файл не выдан.", status=409)
    response = HttpResponse(content, content_type=version.content_type)
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(version.filename)}"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


def invoice_context(order_id=None):
    active_orders = Order.objects.exclude(state="closed").prefetch_related("lines__product")
    return {
        "available_lots": list(stock.available_lots()), "selected_order": order_id,
        "orders_data": [{"id": order.pk, "customer": order.customer, "kind": order.kind,
                         "lines": [{"id": line.pk, "product": line.product.code, "name": line.product.name,
                                    "quantity": line.quantity, "weight": str(line.weight),
                                    "animal_type": line.type_requirement if order.kind == "live" else "",
                                    "age_min": line.age_min, "age_max": line.age_max,
                                    "purity_min": str(line.purity_min) if line.purity_min is not None else "",
                                    "purity_max": str(line.purity_max) if line.purity_max is not None else ""}
                                   for line in order.lines.all()]} for order in active_orders],
    }


@require_GET
@access_required()
def invoice_new(request):
    context = invoice_context(request.GET.get("order"))
    context["selected_lots"] = request.GET.get("lots", "").split(",")
    return render(request, "inventory/invoice_new.html", context)


@require_GET
@access_required()
def order_list(request):
    result = [{"order": order, "report": orders.fulfillment(order)} for order in Order.objects.all().prefetch_related("lines__product")]
    return render(request, "inventory/orders.html", {"orders": result})


@require_GET
@access_required()
def order_new(request):
    return render(request, "inventory/order_new.html", {
        "products": list(Product.objects.values("code", "name", "category", "counted")),
        "animal_types": [("", "Любой тип"), *ANIMAL_TYPE_CHOICES],
    })


@require_GET
@access_required()
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, "inventory/order_detail.html", {"order": order, "report": orders.fulfillment(order)})


@require_GET
@access_required()
def cut_page(request, pk):
    lot = get_object_or_404(StockLot.objects.select_related("animal", "product"), pk=pk)
    weight, quantity = stock.balance(lot)
    return render(request, "inventory/cut.html", {"lot": lot, "weight": weight, "quantity": quantity,
        "products": list(Product.objects.filter(category="meat").values("code", "name", "category", "counted"))})


@api
def receipt_prepare_api(request, data):
    return document_result(receipts.prepare_receipt(request.user, data.get("tags"), kind=data.get("kind"),
        document_id=data.get("document_id"), expected_revision=data.get("revision")))


@api
def receipt_save_api(request, data, pk):
    return document_result(receipts.save_receipt(request.user, pk, payload=data.get("payload"),
        expected_revision=data.get("revision"), number=data.get("number", ""),
        upload=request.FILES.get("file"), reason=data.get("reason", ""),
        replace_confirmed=data.get("replace_confirmed") is True, submit=data.get("submit") is True))


@api
def confirm_api(request, data, pk):
    require_inventory(request.user)
    if data.get("numbers_verified") is not True:
        raise ValidationError("Подтвердите, что вы проверили файл и все количественные данные.")
    doc = Document.objects.get(pk=pk)
    if doc.kind == "invoice":
        return document_result(invoices.confirm_invoice(request.user, pk, expected_revision=data.get("revision"),
            keep_open=data.get("keep_open") is True, close=data.get("close", True) is True))
    return document_result(receipts.confirm_receipt(request.user, pk, expected_revision=data.get("revision")))


@api
def invoice_save_api(request, data):
    return document_result(invoices.save_invoice(request.user, payload=data.get("payload"), order_id=data.get("order_id"),
        document_id=data.get("document_id"), expected_revision=data.get("revision"), number=data.get("number", ""),
        upload=request.FILES.get("file"), reason=data.get("reason", ""), replace_confirmed=data.get("replace_confirmed") is True))


@api
def reverse_api(request, data, pk):
    return document_result(invoices.reverse_invoice(request.user, pk, reason=data.get("reason", ""), expected_revision=data.get("revision")))


@api
def order_create_api(request, data):
    order = orders.create_order(request.user, data)
    return {"id": order.pk, "url": reverse("inventory:order", args=[order.pk])}


@api
def order_close_api(request, data, pk):
    order = orders.close_order(request.user, pk)
    return {"url": reverse("inventory:order", args=[order.pk])}


@api
def cut_api(request, data, pk):
    stock.cut_lot(request.user, pk, weight=data.get("weight"), quantity=data.get("quantity"),
                  outputs=data.get("outputs"), loss_weight=data.get("loss_weight", "0"), reason=data.get("reason", ""),
                  expected_balance=(data.get("expected_weight"), data.get("expected_quantity")))
    return {"url": reverse("inventory:stock")}


@api
def replace_file_api(request, data, pk):
    from django.db import transaction
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=pk)
        document_access(request.user, doc)
        assert_revision(doc, data.get("revision"))
        assert_editable(doc)
        if not request.FILES.get("file"):
            raise ValidationError("Выберите исправленный файл.")
        add_version(doc, request.user, upload=request.FILES["file"], reason=data.get("reason", ""),
                    replace_confirmed=data.get("replace_confirmed") is True)
    return document_result(doc)


@api
def return_to_vet_api(request, data, pk):
    from django.db import transaction
    require_inventory(request.user)
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=pk)
        assert_revision(doc, data.get("revision"))
        assert_editable(doc)
        if doc.kind != "sp55" or not str(data.get("reason", "")).strip():
            raise ValidationError("Укажите причину возврата СП-55 ветврачу.")
        doc.state = "draft"
        # Bump the revision as well: an already open approval page cannot
        # approve an obsolete review state after return/resubmission.
        add_version(doc, request.user, reason="Возврат ветврачу: " + data["reason"])
        AuditEvent.objects.create(document=doc, actor=request.user, action="returned_to_vet", data={"reason": data["reason"]})
    return document_result(doc)
