"""Clinical commands. Lock order: tags, animals/episodes, then the medicine ledger."""
import uuid
from decimal import Decimal
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from begunici.app_types.animals.models import Maker, Ram, Ewe, Sheep
from begunici.app_types.animals.models_user_log import UserActionLog
from begunici.app_types.veterinary.vet_models import Tag, Place
from begunici.app_types.vet_inventory.models import VetSettings, VetDocument
from begunici.app_types.vet_inventory.services import normalize_lines, add_version, apply_movements, audit, number, text, valid_date
from .models import Episode, Event, Dose
from .permissions import require_manage, require_admit

ANIMALS = (Maker, Ram, Ewe, Sheep)
LABELS = {"Maker": "Баран-производитель", "Ram": "Баранчик", "Ewe": "Ярка", "Sheep": "Овцематка"}


def clinical_audit(user, action, episode, description, **data):
    if not getattr(user, "is_authenticated", False):
        return
    UserActionLog.objects.create(
        user=user, action_type=action, object_type="История болезни", object_id=str(episode.pk),
        description=f"Бирка {episode.tag_number}; {description}",
        additional_data={"clinical_episode_id": episode.pk, "tag_id": episode.tag_id, **data},
    )


def animal_for(tag_id, locked=False):
    for model in ANIMALS:
        qs = model.objects.select_related("tag", "place", "animal_status")
        if locked:
            # Avoid PostgreSQL FOR UPDATE on nullable joins.
            qs = qs.select_for_update(of=("self",))
        animal = qs.filter(tag_id=tag_id).first()
        if animal:
            return animal
    raise ValidationError("Животное не найдено. История болезни сохранена.")


def animal_snapshot(animal):
    from dateutil.relativedelta import relativedelta
    today = timezone.localdate()
    if not isinstance(animal, (Ram, Ewe)):
        subgroup = "Взрослое"
    elif animal.birth_date and animal.birth_date > today - relativedelta(months=1):
        subgroup = "До 1 мес."
    elif animal.birth_date and animal.birth_date >= today - relativedelta(months=3):
        subgroup = "1–3 мес., отбито" if animal.date_otbivka else "1–3 мес., не отбито"
    else:
        subgroup = "Старше 3 мес."
    return {"tag": animal.tag.tag_number, "type": animal.get_animal_type(), "label": LABELS[animal.get_animal_type()], "sex": "Мужской" if isinstance(animal, (Maker, Ram)) else "Женский", "subgroup": subgroup, "birth_date": animal.birth_date.isoformat() if animal.birth_date else None, "age": animal.get_age_display(), "place": str(animal.place or "")}


def change_animal(user, animal, data):
    from begunici.app_types.animals.serializers import MakerSerializer, RamSerializer, EweSerializer, SheepSerializer
    serializer_class = {Maker: MakerSerializer, Ram: RamSerializer, Ewe: EweSerializer, Sheep: SheepSerializer}[type(animal)]
    serializer = serializer_class(animal, data=data, partial=True, context={"request": SimpleNamespace(user=user)})
    serializer.is_valid(raise_exception=True)
    return serializer.save()


def ensure_episode(animal, user):
    user = user if getattr(user, "is_authenticated", False) else None
    episode, created = Episode.objects.get_or_create(tag_id=animal.tag_id, closed_on__isnull=True, defaults={"snapshot": animal_snapshot(animal), "origin": str(animal.place or ""), "created_by": user})
    if created:
        clinical_audit(user, "Направление на лечение", episode, f"поступление {episode.admitted_on:%d.%m.%Y}; место: {episode.origin or 'не указано'}")
    return episode


def lock_episode(pk, revision=None, allow_closed=False):
    base = Episode.objects.get(pk=pk)
    if base.tag_id:
        Tag.objects.select_for_update().get(pk=base.tag_id)
    episode = Episode.objects.select_for_update().get(pk=pk)
    if episode.closed_on and not allow_closed:
        raise ValidationError("Лечение уже завершено. История доступна только для просмотра.")
    if revision is not None and str(episode.revision) != str(revision):
        raise ValidationError("Запись изменилась. Обновите страницу и проверьте данные.")
    return episode


def checked_date(value, episode):
    result = valid_date(value)
    if result < episode.admitted_on:
        raise ValidationError("Дата мероприятия не может предшествовать поступлению.")
    return result


def event_token(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Обновите форму перед сохранением.")


@transaction.atomic
def admit(user, tag_id):
    require_admit(user)
    try:
        tag_id = int(tag_id)
        Tag.objects.select_for_update().get(pk=tag_id)
    except (Tag.DoesNotExist, ValueError, TypeError):
        raise ValidationError("Выберите существующее животное.")
    animal = animal_for(tag_id, locked=True)
    if animal.is_archived:
        raise ValidationError("Архивное животное нельзя направить на лечение.")
    if not animal.is_in_treatment:
        animal.is_in_treatment = True
        from .bridge import completing
        with completing():
            animal.save()
    return ensure_episode(animal, user)


@transaction.atomic
def update_intake(user, pk, revision, diagnosis, admitted_on, place_id, confirm_group_move=False):
    require_manage(user)
    episode = lock_episode(pk, revision)
    animal = animal_for(episode.tag_id, locked=True)
    date = valid_date(admitted_on)
    if animal.birth_date and date < animal.birth_date:
        raise ValidationError("Поступление не может предшествовать рождению животного.")
    if episode.events.filter(kind="care", date__lt=date).exists():
        raise ValidationError("Поступление не может быть позже уже зарегистрированного мероприятия.")
    old = {"diagnosis": episode.diagnosis, "admitted_on": str(episode.admitted_on), "place": str(animal.place or "")}
    episode.diagnosis, episode.admitted_on = text(diagnosis, "Диагноз", 1000, False), date
    if place_id:
        try:
            place = Place.objects.get(pk=place_id)
        except (Place.DoesNotExist, ValueError, TypeError):
            raise ValidationError("Выберите место из справочника.")
        if animal.place_id != place.pk:
            animal = change_animal(user, animal, {"place_id": place.pk, "confirm_group_place_move": confirm_group_move})
    episode.revision += 1
    episode.save()
    Event.objects.create(episode=episode, kind="intake", date=timezone.localdate(), note="Уточнены данные поступления", details={"before": old, "after": {"diagnosis": episode.diagnosis, "admitted_on": str(date), "place": str(animal.place or "")}}, created_by=user)
    clinical_audit(user, "Уточнение поступления на лечение", episode,
                   f"диагноз: {episode.diagnosis or 'не указан'}; дата поступления: {date:%d.%m.%Y}; место: {animal.place or 'не указано'}", before=old)
    return episode


@transaction.atomic
def add_care(user, selections, date, note, rows, mode, token):
    require_manage(user)
    token = event_token(token)
    if mode not in {"head", "group"}:
        raise ValidationError("Выберите расход на голову или на группу.")
    if not isinstance(selections, list) or not 1 <= len(selections) <= 200:
        raise ValidationError("Выберите от 1 до 200 животных.")
    try:
        selected = {int(row["id"]): row["revision"] for row in selections}
    except (TypeError, ValueError, KeyError):
        raise ValidationError("Проверьте список животных.")
    if len(selected) != len(selections):
        raise ValidationError("Животное выбрано дважды.")
    bases = list(Episode.objects.filter(pk__in=selected).order_by("tag_id"))
    if len(bases) != len(selected):
        raise ValidationError("Запись журнала не найдена.")
    list(Tag.objects.select_for_update().filter(pk__in=[e.tag_id for e in bases]).order_by("pk"))
    # A repeated form submission is an idempotent success; a partial overlap is rejected.
    existing = Event.objects.filter(episode_id__in=selected, token=token).count()
    if existing:
        if existing == len(selected):
            return
        raise ValidationError("Часть группы уже обработана этой формой. Обновите страницу.")
    episodes = [lock_episode(e.pk, selected[e.pk]) for e in bases]
    note = text(note, "Действия, исследования или рекомендации", 12000)
    # Shared lock freezes product units and names against catalog changes.
    VetSettings.objects.select_for_update().get(pk=1)
    lines = normalize_lines(rows, allow_empty=True)
    count = len(episodes)
    for index, episode in enumerate(episodes):
        animal = animal_for(episode.tag_id, locked=True)
        if animal.is_archived or not animal.is_in_treatment:
            raise ValidationError("Животное больше не находится на лечении.")
        event = Event.objects.create(episode=episode, date=checked_date(date, episode), note=note, token=token, created_by=user, details={"mode": mode, "heads": count, "entered_lines": lines})
        for line in lines:
            quantity = Decimal(line["amount"])
            if mode == "group":
                milli, remainder = divmod(int(quantity * 1000), count)
                quantity = Decimal(milli + (index < remainder)) / 1000
            if quantity:
                Dose.objects.create(event=event, product_id=line["product"], name=line["name"], unit=line["unit"], quantity=quantity)
        episode.revision += 1
        episode.save(update_fields=["revision"])
        consumption = "; ".join(f"{dose.name}: {number(dose.quantity)} {dose.unit}" for dose in event.doses.all())
        clinical_audit(user, "Лечебное мероприятие", episode,
                       f"{event.date:%d.%m.%Y}; {note}; расход: {consumption or 'без препаратов'}", event_id=event.pk)


def totals(episode):
    result = {}
    for dose in Dose.objects.filter(event__episode=episode).order_by("pk"):
        line = result.setdefault(dose.product_id, {"product": dose.product_id, "name": dose.name, "unit": dose.unit, "quantity": Decimal(0)})
        line["quantity"] += dose.quantity
    return [{"product": r["product"], "name": r["name"], "unit": r["unit"], "amount": number(r["quantity"]), "packages": "0"} for r in result.values()]


def post_clinical_expense(user, episode):
    document = episode.expense_document
    if not document or document.state == "posted":
        return
    if document.state != "draft":
        raise ValidationError("Документ расхода отменён или сторнирован. Проверьте складской учёт.")
    try:
        with transaction.atomic():
            apply_movements(document, document.versions.first().payload["lines"], -1)
            document.state, document.posted_at, document.posted_by = "posted", timezone.now(), user
            document.save(update_fields=["state", "posted_at", "posted_by"])
            audit(user, "Подтверждён расход лечения", document=document.pk, clinical_episode=episode.pk)
        episode.expense_issue = ""
    except ValidationError as exc:
        episode.expense_issue = "; ".join(exc.messages)
    episode.save(update_fields=["expense_issue"])


@transaction.atomic
def close_episode(user, pk, revision, outcome, closed_on, rows, reason, status_id, confirm_status, archive=None):
    require_manage(user)
    episode = lock_episode(pk, allow_closed=True)
    if episode.closed_on:
        return episode  # Repeat discharge cannot charge stock a second time.
    if str(episode.revision) != str(revision):
        raise ValidationError("Запись изменилась. Обновите страницу перед завершением.")
    if not confirm_status:
        raise ValidationError("Подтвердите текущий или выбранный статус животного.")
    animal = animal_for(episode.tag_id, locked=True)
    date = checked_date(closed_on, episode)
    if episode.events.filter(kind="care", date__gt=date).exists():
        raise ValidationError("Дата выписки не может быть раньше последнего мероприятия.")
    outcome = text(outcome, "Исход лечения", 4000)
    if not episode.diagnosis.strip():
        raise ValidationError("Перед завершением укажите диагноз в данных поступления.")
    expected = totals(episode)
    VetSettings.objects.select_for_update().get(pk=1)
    confirmed = normalize_lines(rows, allow_empty=True)
    reason = text(reason, "Причина корректировки расхода", 2000, False)
    def quantities(lines):
        return {r["product"]: Decimal(r["amount"]) for r in lines}
    if quantities(expected) != quantities(confirmed) and not reason:
        raise ValidationError("Расход изменён. Укажите причину корректировки.")
    if archive is not None and not isinstance(archive, dict):
        raise ValidationError("Проверьте данные архивации.")
    from .bridge import completing
    # Reuse the existing serializer, including status rules, archive acts and history.
    data = {"is_in_treatment": False}
    if status_id:
        data["animal_status_id"] = status_id
        data["status_date"] = str(date)
    allowed = {"archive_act_date", "archive_act_fatness", "archive_act_death_reason", "archive_act_diagnosis", "archive_act_live_weight", "archive_act_weight_date", "archive_act_worker_name", "carcass_weight", "is_for_sale"}
    data.update({k: v for k, v in (archive or {}).items() if k in allowed and v not in (None, "")})
    with completing():
        animal = change_animal(user, animal, data)
    episode.snapshot = {**episode.snapshot, "discharge_place": str(animal.place or ""), "discharge_status": str(animal.animal_status or "")}
    episode.closed_on, episode.outcome = date, outcome
    episode.closed_at, episode.closed_by = timezone.now(), user
    episode.expense_expected, episode.expense_confirmed = expected, confirmed
    episode.revision += 1
    if confirmed:
        document = VetDocument.objects.create(kind="consume", date=date, created_by=user)
        add_version(document, user, {"lines": confirmed, "note": f"Лечение № {episode.pk}, бирка {episode.tag_number}. {outcome}" + (f" Корректировка: {reason}" if reason else ""), "clinical_episode": episode.pk, "expected": expected, "adjustment_reason": reason})
        episode.expense_document = document
    episode.save()
    Event.objects.create(episode=episode, kind="discharge", date=date, note=outcome, created_by=user, details={"expected": expected, "confirmed": confirmed, "reason": reason, "status": str(animal.animal_status or "Не указан")})
    post_clinical_expense(user, episode)
    expense_state = "требует сверки" if episode.stock_pending else ("учтён" if confirmed else "без препаратов")
    clinical_audit(user, "Завершение лечения", episode,
                   f"{date:%d.%m.%Y}; исход: {outcome}; статус: {animal.animal_status or 'не указан'}; расход: {expense_state}",
                   expected=expected, confirmed=confirmed, adjustment_reason=reason)
    return episode


@transaction.atomic
def reconcile(user, pk):
    require_manage(user)
    episode = lock_episode(pk, allow_closed=True)
    if not episode.closed_on:
        raise ValidationError("Итоговый расход подтверждается после завершения лечения.")
    VetSettings.objects.select_for_update().get(pk=1)
    if episode.expense_document_id:
        episode.expense_document = VetDocument.objects.select_for_update().get(pk=episode.expense_document_id)
    was_pending = episode.stock_pending
    post_clinical_expense(user, episode)
    if was_pending:
        clinical_audit(user, "Сверка расхода лечения", episode,
                       f"расход: {'требует сверки; ' + episode.expense_issue if episode.stock_pending else 'учтён'}")
    return episode
