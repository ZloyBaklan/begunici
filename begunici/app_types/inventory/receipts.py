from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from . import bridges
from .documents import add_version, assert_editable, assert_revision
from .models import AnimalCase, AuditEvent, Document, Product, StockLot, StockMovement
from .permissions import require_inventory, require_slaughter
from .validation import amount, count, rows


def _check_permission(user, kind):
    (require_slaughter if kind == "sp55" else require_inventory)(user)


@transaction.atomic
def prepare_receipt(user, tag_ids, *, kind, document_id=None, expected_revision=None):
    _check_permission(user, kind)
    if kind not in {"sp54", "sp55"}:
        raise ValidationError("Неизвестный вид акта.")
    if not isinstance(tag_ids, list) or not tag_ids or len(tag_ids) > 200:
        raise ValidationError("Выберите от 1 до 200 животных.")
    sources = [bridges.source_info(bridges.source_animal(count(tag, "Идентификатор"))) for tag in set(tag_ids)]
    # SP-54 already may be one shared act: approval applies to its full group.
    if kind == "sp54":
        groups = {source["group_key"] for source in sources if source["group_key"]}
        if len(groups) > 1 or (groups and any(not source["group_key"] for source in sources)) or (not groups and len(sources) > 1):
            raise ValidationError("СП-54 оформляется по одному исходному акту или его общей группе.")
        if groups:
            group_key = groups.pop()
            from begunici.app_types.animals.models import ArchiveAct
            tags = ArchiveAct.objects.filter(act_group_key=group_key).values_list("tag_id", flat=True)
            sources = [bridges.source_info(bridges.source_animal(tag)) for tag in tags]
    for source in sources:
        bridges.require_eligible(source)
        if source["kind"] != ("live" if kind == "sp54" else "meat"):
            raise ValidationError("Нельзя смешать реализацию живьём и убой в одном акте.")
    if document_id:
        document = Document.objects.select_for_update().get(pk=document_id)
        assert_revision(document, expected_revision)
        assert_editable(document)
        if document.kind != "sp55" or kind != "sp55":
            raise ValidationError("Дополнять животными можно только СП-55.")
    else:
        # Repeated clicks on the same animal reopen its existing document.
        existing = list(AnimalCase.objects.filter(source_tag_id__in=[source["tag_id"] for source in sources]))
        if existing:
            if len(existing) == len(sources) and len({case.receipt_id for case in existing}) == 1:
                return existing[0].receipt
            raise ValidationError("Часть выбранных животных уже привязана к другому складскому акту.")
        document = Document.objects.create(kind=kind, created_by=user, payload={"animals": {}, "outputs": []})
    for source in sources:
        if AnimalCase.objects.filter(source_tag_id=source["tag_id"]).exists():
            raise ValidationError(f"{source['tag_number']}: уже есть складской акт.")
        case = AnimalCase.objects.create(
            source_tag_id=source["tag_id"], tag_number=source["tag_number"], animal_type=source["animal_type"],
            kind=source["kind"], archive_date=source["archive_date"], source_fingerprint=source["fingerprint"],
            snapshot=source["snapshot"], receipt=document,
        )
        snapshot = source["snapshot"]
        document.payload["animals"][str(case.pk)] = {
            "weight": snapshot.get("live_weight") or snapshot.get("last_weight") or "",
            "fatness": snapshot.get("fatness", ""), "comment": snapshot.get("vet_comment", ""),
        }
        if kind == "sp54":
            document.payload["outputs"].append({
                "animal_id": case.pk, "product": "live", "quantity": 1,
                "weight": snapshot.get("live_weight") or "", "rejected": False, "reason": "",
            })
    document.state = "ready" if kind == "sp54" else "draft"
    original = bridges.original_sp54(bridges.source_animal(sources[0]["tag_id"]), user) if kind == "sp54" else None
    add_version(document, user, content=original, reason="Исходный акт" if kind == "sp54" else "Подготовлен СП-55")
    return document


def normalize_receipt_payload(document, payload, *, complete=False):
    if not isinstance(payload, dict):
        raise ValidationError("Некорректные данные акта.")
    cases = {case.pk: case for case in document.animals.all()}
    products = {product.code: product for product in Product.objects.all()}
    result = {"animals": {}, "outputs": []}
    animal_values = payload.get("animals", {})
    if not isinstance(animal_values, dict):
        raise ValidationError("Некорректные данные животных.")
    for case_id, case in cases.items():
        details = animal_values.get(str(case_id), {})
        if not isinstance(details, dict):
            raise ValidationError("Некорректные данные животного.")
        weight = details.get("weight", "")
        fatness, comment = str(details.get("fatness", "")).strip(), str(details.get("comment", "")).strip()
        if document.kind == "sp55" and complete and (not fatness or not comment):
            raise ValidationError(f"{case.tag_number}: заполните упитанность и заключение ветврача.")
        result["animals"][str(case_id)] = {
            "weight": str(amount(weight)) if weight not in (None, "") else "",
            "fatness": fatness[:200], "comment": comment[:3000],
        }
        if complete and document.kind == "sp55" and not result["animals"][str(case_id)]["weight"]:
            raise ValidationError(f"{case.tag_number}: не указана живая масса.")
    output_rows = payload.get("outputs", [])
    if complete:
        rows(output_rows)
    elif not isinstance(output_rows, list) or len(output_rows) > 500:
        raise ValidationError("Некорректные строки выхода продукции.")
    per_animal = {case_id: [] for case_id in cases}
    seen = set()
    for item in output_rows:
        if not isinstance(item, dict):
            raise ValidationError("Некорректная строка выхода.")
        animal_id = count(item.get("animal_id"), "Животное")
        if animal_id not in cases:
            raise ValidationError("Продукция относится к животному из другого акта.")
        product = products.get(item.get("product"))
        if not product or (product.category == "live") != (document.kind == "sp54"):
            raise ValidationError("Неверная номенклатура для этого вида акта.")
        weight = amount(item.get("weight"))
        quantity = count(item.get("quantity", 0), allow_zero=not product.counted)
        if not product.counted and quantity:
            raise ValidationError("Весовая продукция учитывается в килограммах; количество штук должно быть нулевым.")
        rejected = item.get("rejected") is True
        reason = str(item.get("reason", "")).strip()[:3000]
        if rejected and not reason:
            raise ValidationError("Для забракованной продукции укажите причину.")
        if product.code == "testes" and cases[animal_id].snapshot.get("sex") != "male":
            raise ValidationError("Семенники можно указать только у барана.")
        key = (animal_id, product.code, rejected)
        if key in seen:
            raise ValidationError("Объедините одинаковую номенклатуру одного животного в одну строку.")
        seen.add(key)
        clean = {"animal_id": animal_id, "product": product.code, "weight": str(weight),
                 "quantity": quantity, "rejected": rejected, "reason": reason}
        result["outputs"].append(clean)
        per_animal[animal_id].append((product, clean))
    for case_id, outputs in per_animal.items():
        case = cases[case_id]
        if complete and not outputs:
            raise ValidationError(f"{case.tag_number}: укажите выход или брак продукции.")
        if document.kind == "sp54":
            if len(outputs) != 1 or outputs[0][1]["quantity"] != 1 or outputs[0][1]["rejected"]:
                raise ValidationError("Для СП-54 нужна ровно одна голова на каждое животное.")
        else:
            meat = [(product, row) for product, row in outputs if product.category == "meat"]
            codes = {product.code for product, row in meat}
            if ("carcass" in codes and len(codes) > 1) or ("half" in codes and len(codes) > 1):
                raise ValidationError(f"{case.tag_number}: нельзя одновременно оприходовать тушу/полутуши и их части. Используйте разделку.")
            for code, maximum in [("carcass", 1), ("half", 2)]:
                if sum(row["quantity"] for product, row in meat if product.code == code) > maximum:
                    raise ValidationError(f"{case.tag_number}: максимум {maximum} для «{products[code].name}».")
            live = result["animals"][str(case_id)]["weight"]
            total_weight = sum((Decimal(row["weight"]) for product, row in outputs), Decimal(0))
            if live and total_weight > Decimal(live):
                raise ValidationError(f"{case.tag_number}: выход вместе с браком превышает живую массу.")
            carcass = case.snapshot.get("carcass_weight")
            if carcass and sum((Decimal(row["weight"]) for product, row in meat), Decimal(0)) > Decimal(carcass):
                raise ValidationError(f"{case.tag_number}: мясо вместе с браком превышает указанную в архиве массу туши.")
    return result


@transaction.atomic
def save_receipt(user, document_id, *, payload, expected_revision, number="", upload=None, reason="", replace_confirmed=False, submit=False):
    document = Document.objects.select_for_update().get(pk=document_id)
    _check_permission(user, document.kind)
    if document.kind not in {"sp54", "sp55"}:
        raise ValidationError("Это не акт поступления.")
    assert_editable(document)
    assert_revision(document, expected_revision)
    document.payload = normalize_receipt_payload(document, payload, complete=submit)
    document.number = str(number).strip()[:100]
    if submit and document.kind == "sp55" and upload is None:
        raise ValidationError("Для передачи СП-55 на проверку приложите заполненный акт ветврача.")
    if document.kind == "sp54" and upload is None:
        raise ValidationError("При исправлении данных СП-54 приложите исправленный акт.")
    document.state = "ready" if submit or document.kind == "sp54" else "draft"
    add_version(document, user, upload=upload, reason=reason, replace_confirmed=replace_confirmed)
    return document


@transaction.atomic
def confirm_receipt(user, document_id, *, expected_revision):
    require_inventory(user)
    document = Document.objects.select_for_update().get(pk=document_id)
    assert_revision(document, expected_revision)
    if document.kind not in {"sp54", "sp55"}:
        raise ValidationError("Это не акт поступления.")
    if document.state == "confirmed":
        return document
    if document.state != "ready":
        raise ValidationError("Сначала передайте заполненный акт на проверку.")
    normalized = normalize_receipt_payload(document, document.payload, complete=True)
    if document.kind == "sp55" and document.versions.get(number=document.revision).origin != "uploaded":
        raise ValidationError("Ветврач должен подгрузить заполненный СП-55.")
    cases = {case.pk: case for case in document.animals.all()}
    for case in cases.values():
        bridges.validate_case_source(case)
    products = {product.code: product for product in Product.objects.all()}
    for row in normalized["outputs"]:
        if row["rejected"]:
            continue
        lot = StockLot.objects.create(animal=cases[row["animal_id"]], product=products[row["product"]])
        StockMovement.objects.create(lot=lot, kind="receipt", weight=row["weight"], quantity=row["quantity"], document=document, created_by=user)
    document.state = "confirmed"
    document.confirmed_by = user
    document.confirmed_at = timezone.now()
    document.save(update_fields=["state", "confirmed_by", "confirmed_at"])
    AuditEvent.objects.create(document=document, actor=user, action="receipt_confirmed", data={"revision": document.revision})
    return document
