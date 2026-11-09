"""Barn feed subledger for deliveries, writeoffs and confirmed consumption."""
import hashlib
import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid5

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from begunici.app_types.inventory.documents import read_upload
from begunici.app_types.inventory.permissions import require_inventory
from begunici.app_types.inventory.validation import amount
from begunici.app_types.veterinary.vet_models import Place
from .models import BarnFeedDocument, BarnFeedMovement, BarnFeedPeriod, FeedDocument, FeedProduct, FeedSettings
from . import services
from .plan import build_plan, number
from .packaging import group_map

ZERO = Decimal(0)


def can_view_barns(user):
    return bool(user.is_authenticated and user.is_active and (user.is_superuser or
        user.username in {"admin", "vet", "finans", "main"} or user.groups.filter(name__in=["Admin", "Vet", "Main"]).exists()))


def can_supply(user):
    return can_view_barns(user) and user.username != "main"


def require_supply(user, *, write=True):
    if not (can_supply(user) if write else can_view_barns(user)):
        raise PermissionDenied("Нет доступа к изменению кормового учёта." if write else "Нет доступа к кормовому учёту.")


def barn_number(value):
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise ValidationError("Выберите овчарню.")
    if result not in range(1, 5):
        raise ValidationError("Выберите овчарню от 1 до 4.")
    return result


def place_barn(text):
    match = re.search(r"овчарня\s*(\d+)", str(text or ""), re.I)
    return int(match[1]) if match else None


def places_by_barn():
    result = {i: [] for i in range(1, 5)}
    for pk, label in Place.objects.values_list("pk", "sheepfold"):
        if place_barn(label) in result:
            result[place_barn(label)].append(pk)
    return result


def month_date(value=None):
    try:
        return date.fromisoformat(str(value)[:7] + "-01") if value else timezone.localdate().replace(day=1)
    except ValueError:
        raise ValidationError("Укажите месяц в формате ГГГГ-ММ.")


def month_end(month):
    return month.replace(day=monthrange(month.year, month.month)[1])


def barn_balances(barn, *, before=None, through=None):
    query = BarnFeedMovement.objects.filter(document__barn=barn)
    if before:
        query = query.filter(document__date__lt=before)
    if through:
        query = query.filter(document__date__lte=through)
    return {r["product_id"]: (r["amount"] or ZERO, r["packages"] or ZERO) for r in query.values("product_id").annotate(amount=Sum("amount"), packages=Sum("packages"))}


def ensure_period(barn, today=None):
    today = today or timezone.localdate()
    month = today.replace(day=1)
    existing = BarnFeedPeriod.objects.filter(barn=barn, month=month).first()
    if existing:
        return existing
    if today < timezone.localdate():
        from .barn_forecast import daily_headcounts
        plan = build_plan(today, headcounts=daily_headcounts(barn, today, today)[today])
    else:
        plan = build_plan(today, place_ids=places_by_barn()[barn])
    return BarnFeedPeriod.objects.get_or_create(barn=barn, month=month, defaults={"plan": plan})[0]


def active_weeks(barn):
    return BarnFeedDocument.objects.filter(barn=barn, kind="week", reversal__isnull=True)


def assert_open(barn, document_date, *, weeks=True):
    closed = BarnFeedPeriod.objects.filter(barn=barn, closing__isnull=False,
        month__gte=document_date.replace(day=1)).order_by("-month").first()
    if closed:
        raise ValidationError(f"Овчарня {barn}: операция затронет закрытый месяц {closed.month:%m.%Y}. Сначала сторнируйте сверку.")
    if weeks:
        week = active_weeks(barn).filter(date__gte=document_date).order_by("-date").first()
        if week:
            raise ValidationError(f"Овчарня {barn}: операция затронет подтверждённый расход по {week.date:%d.%m.%Y}. Сначала сторнируйте недельную сверку.")


def _central(user, lines, sign, day, note, reversal_of=None):
    doc = FeedDocument.objects.create(kind="reversal" if reversal_of else ("transfer" if sign < 0 else "barn_return"), state="posted", date=day,
        created_by=user, posted_by=user, posted_at=timezone.now(), reversal_of=reversal_of)
    services.add_version(doc, user, {"lines": lines, "note": note})
    services.apply_movements(doc, lines, sign)
    return doc


def _line_quantities(lines):
    return sorted((line["product"], Decimal(line["amount"]), Decimal(line["packages"])) for line in lines)


@transaction.atomic
def move(user, barn, kind, day, rows, note, request_token, upload=None, *, batch_barns=None):
    require_supply(user)
    FeedSettings.objects.select_for_update().get(pk=1)
    barn, day = barn_number(barn), services.valid_date(day)
    request_token = services.token(request_token)
    if kind not in {"delivery", "return", "writeoff"}:
        raise ValidationError("Неизвестная операция.")
    if kind == "writeoff":
        require_inventory(user)
    lines = services.normalize_lines(rows)
    note = services.text(note, "Основание", 2000)
    attachment = {}
    if upload:
        data, filename, content_type = read_upload(upload)
        attachment = {"content": data, "filename": filename, "content_type": content_type, "sha256": hashlib.sha256(data).hexdigest()}
    if kind == "writeoff" and not attachment:
        raise ValidationError("Для списания приложите акт PDF или XLSX.")
    existing = BarnFeedDocument.objects.filter(token=request_token).first()
    if existing:
        if (existing.barn != barn or existing.kind != kind or existing.created_by_id != user.pk
                or existing.date != day or existing.payload["note"] != note
                or existing.payload.get("batch_barns") != batch_barns
                or existing.sha256 != attachment.get("sha256", "")
                or _line_quantities(existing.payload["lines"]) != _line_quantities(lines)
                or BarnFeedDocument.objects.filter(reversal_of=existing).exists()):
            raise ValidationError("Идентификатор уже использован для другой или отменённой операции. Обновите страницу.")
        return existing
    assert_open(barn, day)
    if kind != "delivery":
        services.validate_dated_debit(BarnFeedMovement.objects.filter(document__barn=barn), lines, day, f"в овчарне {barn}")
    central = _central(user, lines, -1 if kind == "delivery" else 1, day, f"Овчарня {barn}: {note}") if kind != "writeoff" else None
    payload = {"lines": lines, "note": note}
    if batch_barns is not None:
        payload["batch_barns"] = batch_barns
    doc = BarnFeedDocument.objects.create(barn=barn, kind=kind, date=day, token=request_token,
        central_document=central, payload=payload, created_by=user, **attachment)
    sign = 1 if kind == "delivery" else -1
    for line in lines:
        BarnFeedMovement.objects.create(document=doc, product_id=line["product"], amount=Decimal(line["amount"]) * sign, packages=Decimal(line["packages"]) * sign)
    ensure_period(barn, day)
    services.audit(user, "Движение кормов овчарни", barn=barn, barn_document=doc.pk, kind=kind, lines=lines, reason=note)
    return doc


@transaction.atomic
def deliver_batch(user, deliveries, day, note, request_token):
    require_supply(user)
    FeedSettings.objects.select_for_update().get(pk=1)
    if not 1 <= len(deliveries) <= 4:
        raise ValidationError("Добавьте от одной до четырёх овчарен.")
    batch_token = services.token(request_token)
    destinations = {}
    for delivery in deliveries:
        barn = barn_number(delivery.get("barn"))
        rows = delivery.get("lines")
        if barn in destinations:
            raise ValidationError(f"Овчарня {barn} указана дважды.")
        if not isinstance(rows, list) or any(not isinstance(line, dict) for line in rows):
            raise ValidationError(f"Овчарня {barn}: проверьте список кормов.")
        destinations[barn] = rows
    first = BarnFeedDocument.objects.filter(token=batch_token).first()
    batch_barns = sorted(destinations)
    if first and first.payload.get("batch_barns") != batch_barns:
        raise ValidationError("Поставка уже проведена с другим списком овчарен. Обновите страницу.")
    return [move(user, barn, "delivery", day, destinations[barn], note,
        batch_token if index == 0 else uuid5(batch_token, str(barn)), batch_barns=batch_barns)
        for index, barn in enumerate(batch_barns)]


def closing_rows(barn, start, end=None):
    end = end or month_end(start)
    opening = barn_balances(barn, before=start)
    available = barn_balances(barn, through=end)
    products = FeedProduct.objects.in_bulk(available)
    result = []
    for pk, (quantity, packages) in available.items():
        if not quantity and not packages and not opening.get(pk, (ZERO, ZERO))[0]:
            continue
        result.append({"product": products[pk], "opening": opening.get(pk, (ZERO, ZERO))[0],
            "available": quantity, "packages": packages})
    return result


def week_dates(value):
    try:
        day = date.fromisoformat(str(value))
    except ValueError:
        raise ValidationError("Выберите дату в неделе расхода.")
    if day >= timezone.localdate():
        raise ValidationError("Выберите дату в завершённой неделе.")
    monday = day - timedelta(days=day.weekday())
    # Keep each reconciliation within one accounting month.
    return max(monday, day.replace(day=1)), min(monday + timedelta(days=6), month_end(day))


def _closing_lines(barn, start, end, values):
    rows = closing_rows(barn, start, end)
    if set(values) != {str(row["product"].pk) for row in rows}:
        raise ValidationError("Проверьте фактический остаток по каждой позиции. Если остаток равен нулю, укажите 0.")
    lines = []
    for row in rows:
        product = row["product"]
        value = values[str(product.pk)]
        remaining = amount(value.get("amount"), "Конечный остаток", allow_zero=True)
        packs = amount(value.get("packages") or 0, "Оставшиеся упаковки", allow_zero=True)
        if remaining > row["available"] or packs > row["packages"]:
            raise ValidationError(f"{product.name}: остаток больше учётного наличия. Сначала оформите пропущенную поставку.")
        lines.append({"product": product.pk, "name": product.name, "unit": product.get_unit_display(), "package": product.package,
            "amount": number(row["available"] - remaining), "packages": number(row["packages"] - packs),
            "opening": number(row["opening"]), "available": number(row["available"]), "closing": number(remaining), "closing_packages": number(packs)})
    services.validate_dated_debit(BarnFeedMovement.objects.filter(document__barn=barn), lines, end, f"в овчарне {barn}")
    return lines


def _record_consumption(user, barn, kind, end, token, payload):
    doc = BarnFeedDocument.objects.create(barn=barn, kind=kind, date=end, token=token, payload=payload, created_by=user)
    for line in payload["lines"]:
        BarnFeedMovement.objects.create(document=doc, product_id=line["product"],
            amount=-Decimal(line["amount"]), packages=-Decimal(line["packages"]))
    return doc


def _repeated_close(user, barn, kind, end, values, note, token):
    existing = BarnFeedDocument.objects.filter(token=token).first()
    if not existing:
        return None
    if (existing.barn != barn or existing.kind != kind or existing.created_by_id != user.pk
            or existing.date != end or existing.payload["note"] != note
            or BarnFeedDocument.objects.filter(reversal_of=existing).exists()):
        raise ValidationError("Идентификатор операции уже используется.")
    if set(values) != {str(line["product"]) for line in existing.payload["lines"]}:
        raise ValidationError("Сверка уже проведена с другим составом кормов.")
    for line in existing.payload["lines"]:
        value = values[str(line["product"])]
        if (amount(value.get("amount"), "Конечный остаток", allow_zero=True) != Decimal(line["closing"])
                or amount(value.get("packages") or 0, "Оставшиеся упаковки", allow_zero=True) != Decimal(line["closing_packages"])):
            raise ValidationError("Сверка уже проведена с другими остатками. Обновите страницу.")
    return existing


@transaction.atomic
def close_month(user, barn, month, values, note, request_token):
    require_inventory(user)
    FeedSettings.objects.select_for_update().get(pk=1)
    barn, month = barn_number(barn), month_date(month)
    end = month_end(month)
    note = services.text(note, "Комментарий сверки", 2000)
    token = services.token(request_token)
    existing = _repeated_close(user, barn, "close", end, values, note, token)
    if existing:
        return existing
    if month_end(month) >= timezone.localdate():
        raise ValidationError("Месяц можно закрыть после его завершения.")
    period = BarnFeedPeriod.objects.select_for_update().filter(barn=barn, month=month).first()
    if not period and BarnFeedMovement.objects.filter(document__barn=barn, document__date__lte=end).exists():
        period = ensure_period(barn, end)
    if not period:
        raise ValidationError("За этот месяц ещё не зафиксирован план. Историческое поголовье автоматически не восстанавливается.")
    if period.closing_id:
        raise ValidationError("Факт за месяц уже подтверждён.")
    if BarnFeedPeriod.objects.filter(barn=barn, month__lt=month, closing__isnull=True).exists():
        raise ValidationError("Сначала закройте предыдущие месяцы этой овчарни.")
    if active_weeks(barn).filter(date__gt=end).exists():
        raise ValidationError("Сначала сторнируйте недельные сверки следующего месяца этой овчарни.")
    lines = _closing_lines(barn, month, end, values)
    doc = _record_consumption(user, barn, "close", end, token,
        {"month": month.isoformat(), "plan": period.plan, "lines": lines, "note": note})
    period.closing = doc
    period.save(update_fields=["closing"])
    services.audit(user, "Подтверждён месячный расход овчарни", barn=barn, barn_document=doc.pk, month=month.isoformat(), lines=lines)
    return doc


@transaction.atomic
def close_week(user, barn, week, values, note, request_token):
    require_inventory(user)
    FeedSettings.objects.select_for_update().get(pk=1)
    barn = barn_number(barn)
    start, end = week_dates(week)
    note = services.text(note, "Комментарий сверки", 2000)
    token = services.token(request_token)
    existing = _repeated_close(user, barn, "week", end, values, note, token)
    if existing:
        return existing
    if end >= timezone.localdate():
        raise ValidationError("Недельный расход можно подтвердить после окончания периода.")
    assert_open(barn, end)
    month = start.replace(day=1)
    if BarnFeedPeriod.objects.filter(barn=barn, month__lt=month, closing__isnull=True).exists():
        raise ValidationError("Сначала закройте предыдущие месяцы этой овчарни.")
    lines = _closing_lines(barn, start, end, values)
    if not lines:
        raise ValidationError("За неделю нет кормов для сверки.")
    ensure_period(barn, start)
    doc = _record_consumption(user, barn, "week", end, token,
        {"start": start.isoformat(), "lines": lines, "note": note})
    services.audit(user, "Подтверждён недельный расход овчарни", barn=barn, barn_document=doc.pk,
        start=start.isoformat(), end=end.isoformat(), lines=lines)
    return doc


@transaction.atomic
def reverse(user, pk, reason):
    require_inventory(user)
    FeedSettings.objects.select_for_update().get(pk=1)
    try:
        doc = BarnFeedDocument.objects.get(pk=int(pk))
    except (ValueError, TypeError, BarnFeedDocument.DoesNotExist):
        raise ValidationError("Операция овчарни не найдена.")
    if doc.kind == "reversal" or BarnFeedDocument.objects.filter(reversal_of=doc).exists():
        raise ValidationError("Документ уже сторнирован.")
    reason = services.text(reason, "Причина", 2000)
    if doc.kind != "close":
        assert_open(doc.barn, doc.date, weeks=doc.kind != "week")
    if doc.kind in {"week", "close"} and active_weeks(doc.barn).filter(date__gt=doc.date).exists():
        raise ValidationError("Сначала сторнируйте более позднюю недельную сверку.")
    if doc.kind == "close" and BarnFeedPeriod.objects.filter(barn=doc.barn, month__gt=doc.date.replace(day=1), closing__isnull=False).exists():
        raise ValidationError("Сначала отмените более позднюю месячную сверку.")
    if doc.kind not in {"close", "week"} and BarnFeedDocument.objects.filter(barn=doc.barn, id__gt=doc.pk, reversal__isnull=True).exclude(kind="reversal").exists():
        raise ValidationError("Сторнируйте операции в обратном порядке, начиная с последней.")
    current = barn_balances(doc.barn)
    for m in doc.movements.all():
        old = current.get(m.product_id, (ZERO, ZERO))
        if old[0] - m.amount < 0 or old[1] - m.packages < 0:
            raise ValidationError("После сторно возникнет отрицательный остаток.")
    if doc.kind == "delivery":
        services.validate_dated_debit(BarnFeedMovement.objects.filter(document__barn=doc.barn),
            doc.payload["lines"], doc.date, f"в овчарне {doc.barn}")
    central = None
    if doc.central_document_id:
        central = _central(user, doc.payload["lines"], 1 if doc.kind == "delivery" else -1,
            timezone.localdate(), reason, reversal_of=doc.central_document)
        doc.central_document.state = "reversed"
        doc.central_document.save(update_fields=["state"])
    reversal = BarnFeedDocument.objects.create(barn=doc.barn, kind="reversal", date=doc.date, reversal_of=doc,
        central_document=central, created_by=user, payload={"note": reason, "lines": doc.payload["lines"]})
    for m in doc.movements.all():
        BarnFeedMovement.objects.create(document=reversal, product_id=m.product_id, amount=-m.amount, packages=-m.packages)
    if doc.kind == "close":
        BarnFeedPeriod.objects.filter(closing=doc).update(closing=None)
    services.audit(user, "Сторно движения овчарни", barn=doc.barn, barn_document=doc.pk, barn_reversal=reversal.pk, reason=reason)
    return reversal


def weekly_movements(barn, today=None):
    from .barn_statistics import weekly_movements as calculate
    return calculate(barn, today)


def summary(barn, today=None, *, capture_plan=False):
    today = today or timezone.localdate()
    month = today.replace(day=1)
    if capture_plan:
        ensure_period(barn, today)
    plan = build_plan(today, place_ids=places_by_barn()[barn])
    mapping = group_map()
    balances = {}
    for pk, (qty, packs) in barn_balances(barn).items():
        root = mapping[pk]
        balances[root] = balances.get(root, ZERO) + qty
    first = BarnFeedDocument.objects.filter(barn=barn, kind="delivery", date__year=today.year, date__month=today.month).order_by("date").first()
    prior = BarnFeedPeriod.objects.filter(barn=barn, month__lt=month, closing__isnull=False).order_by("-month").first()
    estimate_start = month if prior else (first.date if first else today)
    days = max(0, (today - estimate_start).days)
    rows = []
    for item in plan["products"]:
        current = balances.get(item["id"], ZERO)
        consumption = Decimal(item["daily"]) * days
        rows.append({**item, "balance": number(current), "estimate": number(max(ZERO, current - consumption)), "estimated_use": number(consumption)})
    return {"barn": barn, "name": f"Овчарня {barn}", "heads": plan["heads"] + plan["unclassified"], "unclassified": plan["unclassified"],
        "rows": rows, "groups": [r for r in plan["rows"] if r["count"]], "missing": plan["missing"],
        "weekly": weekly_movements(barn, today), "estimate_from": estimate_start.strftime("%d.%m.%Y")}


def comparison(month=None):
    month = month_date(month)
    mapping = group_map()
    roots = {p.pk: p for p in FeedProduct.objects.filter(plan_product__isnull=True)}
    totals = {pk: {"name": p.name, "unit": p.get_unit_display(), "plan": ZERO, "actual": ZERO} for pk, p in roots.items()}
    periods = list(BarnFeedPeriod.objects.filter(month=month).select_related("closing"))
    for period in periods:
        for item in period.plan.get("products", []):
            root = mapping.get(item["id"], item["id"])
            if root in totals: totals[root]["plan"] += Decimal(item["monthly"])
        if period.closing_id:
            for line in period.closing.payload["lines"]:
                root = mapping[line["product"]]
                totals[root]["actual"] += Decimal(line["amount"])
    weeks = list(BarnFeedDocument.objects.filter(kind="week", reversal__isnull=True,
        date__range=(month, month_end(month))).values_list("payload", flat=True))
    for week in weeks:
        for line in week["lines"]:
            totals[mapping[line["product"]]]["actual"] += Decimal(line["amount"])
    for row in totals.values():
        row["difference"] = number(row["actual"] - row["plan"])
        row["over"] = row["actual"] > row["plan"]
        row["percent"] = min(100, round(row["actual"] / row["plan"] * 100)) if row["plan"] else (100 if row["actual"] else 0)
    return {"month": month.strftime("%Y-%m"), "rows": [r for r in totals.values() if r["plan"] > 0 or r["actual"] > 0], "closed": sum(p.closing_id is not None for p in periods),
        "has_actual": bool(weeks) or any(p.closing_id for p in periods),
        "total": 4, "complete": len(periods) == 4 and all(p.closing_id for p in periods),
        "periods": periods}
