from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from begunici.app_types.veterinary.vet_models import Status

from ...models import (
    ARCHIVE_STATUS_NAMES,
    Ewe,
    Lambing,
    LambingGroup,
    Maker,
    Ram,
    Sheep,
    STATUS_FATTENING,
    STATUS_IN_GROUP,
    STATUS_INSEMINATED,
    STATUS_LAMBED,
    STATUS_NOT_INSEMINATED,
    STATUS_REPAIR,
    STATUS_UNDEFINED,
)
from ...status_logic import get_lambing_children, is_young_child_without_weaning


class Command(BaseCommand):
    help = (
        "Пересчитывает статусы животных по текущей логике и переносит старый "
        "статус 'Брак' в отдельный флаг is_reject."
    )

    required_status_names = [
        STATUS_IN_GROUP,
        STATUS_INSEMINATED,
        STATUS_LAMBED,
        STATUS_NOT_INSEMINATED,
        STATUS_UNDEFINED,
        STATUS_FATTENING,
        STATUS_REPAIR,
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет изменено, без записи в базу.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        self.statuses = self._load_statuses()
        self.today = date.today()
        self.updated = 0
        self.reject_marked = 0
        self.unchanged = 0
        self.skipped_archived = 0
        self.warnings = []

        self.stdout.write(
            self.style.WARNING("DRY-RUN: изменения не будут сохранены")
            if dry_run
            else self.style.SUCCESS("Режим применения: изменения будут сохранены")
        )

        with transaction.atomic():
            for model in (Maker, Ram, Ewe, Sheep):
                self._process_model(model, dry_run=dry_run)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Итог:"))
        self.stdout.write(f"  Статус изменится/изменен: {self.updated}")
        self.stdout.write(f"  Отметка Брак выставится/выставлена: {self.reject_marked}")
        self.stdout.write(f"  Без изменений: {self.unchanged}")
        self.stdout.write(f"  Архивные пропущены: {self.skipped_archived}")

        if self.warnings:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Предупреждения:"))
            for warning in self.warnings:
                self.stdout.write(f"  - {warning}")

    def _load_statuses(self):
        statuses = {
            status.status_type: status
            for status in Status.objects.filter(status_type__in=self.required_status_names)
        }
        missing = [
            status_name
            for status_name in self.required_status_names
            if status_name not in statuses
        ]
        if missing:
            raise CommandError("Не найдены обязательные статусы: " + ", ".join(missing))
        return statuses

    def _process_model(self, model, dry_run):
        model_label = self._model_label(model)
        queryset = model.objects.select_related("tag", "animal_status").all().order_by("tag__tag_number")
        self.stdout.write("")
        self.stdout.write(f"{model_label}: {queryset.count()} записей")

        for animal in queryset:
            tag = animal.tag.tag_number if animal.tag else f"id={animal.id}"
            current_status_name = animal.animal_status.status_type if animal.animal_status else None

            if animal.is_archived or current_status_name in ARCHIVE_STATUS_NAMES:
                if current_status_name == "Брак" and not animal.is_reject:
                    self._mark_reject(animal, dry_run, model_label, tag)
                    self.warnings.append(
                        f"{model_label} {tag}: животное архивировано, но статус был 'Брак'. "
                        "Флаг выставлен, статус оставлен без изменений для безопасности."
                    )
                self.skipped_archived += 1
                continue

            reject_changed = False
            if current_status_name == "Брак" and not animal.is_reject:
                reject_changed = self._mark_reject(animal, dry_run, model_label, tag)

            target_status_name, reason = self._get_target_status(animal)
            if not target_status_name:
                if reject_changed:
                    self.unchanged += 1
                else:
                    self.unchanged += 1
                continue

            if target_status_name not in self.statuses:
                self.unchanged += 1
                continue

            target_status = self.statuses[target_status_name]
            if animal.animal_status_id == target_status.id:
                self.unchanged += 1
                continue

            self.updated += 1
            old_display = current_status_name or "нет статуса"
            self.stdout.write(
                f"  {model_label} {tag}: {old_display} -> {target_status_name}; причина: {reason}"
            )

            if not dry_run:
                animal.animal_status = target_status
                animal.save()

    def _mark_reject(self, animal, dry_run, model_label, tag):
        self.reject_marked += 1
        self.stdout.write(f"  {model_label} {tag}: статус 'Брак' перенесен в чекбокс Брак")
        if not dry_run:
            animal.is_reject = True
            animal.save()
        return True

    def _get_target_status(self, animal):
        if isinstance(animal, Ewe):
            return self._get_female_status(animal)
        if isinstance(animal, Sheep):
            return self._get_female_status(animal)
        if isinstance(animal, Ram):
            return self._get_ram_status(animal)
        if isinstance(animal, Maker):
            return self._get_maker_status(animal)
        return None, "неподдерживаемый тип животного"

    def _get_female_status(self, animal):
        if is_young_child_without_weaning(animal, self.today):
            return STATUS_UNDEFINED, "детеныш без отбивки младше 100 дней"

        if self._has_active_group_as_mother(animal):
            return STATUS_INSEMINATED, "мать находится в активной группе"

        if self._has_active_lambing_as_mother(animal):
            return STATUS_INSEMINATED, "есть активная случка после снятия барана"

        latest_lambing = self._latest_completed_lambing_as_mother(animal)
        if not latest_lambing:
            return STATUS_NOT_INSEMINATED, "нет активных и завершенных окотов"

        if latest_lambing.completion_type in Lambing.NON_PRODUCTIVE_COMPLETION_TYPES:
            return STATUS_NOT_INSEMINATED, "последний окот завершен без приплода"

        live_count = latest_lambing.number_of_lambs or 0
        if live_count <= 0:
            return STATUS_NOT_INSEMINATED, "последний окот без живых ягнят"

        children = get_lambing_children(latest_lambing)
        if len(children) < live_count:
            return STATUS_LAMBED, (
                f"последний окот с живыми ягнятами; найдено детей {len(children)} из {live_count}"
            )

        if all(child.date_otbivka or child.is_archived for child in children):
            return STATUS_NOT_INSEMINATED, "все дети последнего окота отбиты или архивированы"

        return STATUS_LAMBED, "есть живые дети последнего окота без отбивки/архива"

    def _get_ram_status(self, animal):
        if LambingGroup.objects.filter(ram=animal, is_active=True).exists():
            return STATUS_IN_GROUP, "баранчик находится в активной группе"

        current_status_name = animal.animal_status.status_type if animal.animal_status else None
        if current_status_name == STATUS_REPAIR:
            return STATUS_REPAIR, "текущий статус Ремонт сохраняется"

        return STATUS_FATTENING, "баранчик без статуса Ремонт"

    def _get_maker_status(self, animal):
        if LambingGroup.objects.filter(maker=animal, is_active=True).exists():
            return STATUS_IN_GROUP, "баран-производитель находится в активной группе"

        current_status_name = animal.animal_status.status_type if animal.animal_status else None
        if current_status_name in {STATUS_IN_GROUP, STATUS_REPAIR, STATUS_FATTENING}:
            return current_status_name, "статус барана-производителя сохраняется"

        if current_status_name in {None, "Брак", "Холостой"}:
            return STATUS_REPAIR, "не удалось сохранить старый рабочий статус, выбран Ремонт"

        self.warnings.append(
            f"Баран-производитель {animal.tag.tag_number if animal.tag else animal.id}: "
            f"нестандартный статус '{current_status_name}' оставлен без изменений"
        )
        return current_status_name, "нестандартный статус сохранен"

    def _has_active_group_as_mother(self, animal):
        if isinstance(animal, Sheep):
            return LambingGroup.objects.filter(sheep=animal, is_active=True).exists()
        return LambingGroup.objects.filter(ewes=animal, is_active=True).exists()

    def _has_active_lambing_as_mother(self, animal):
        if isinstance(animal, Sheep):
            return Lambing.objects.filter(sheep=animal, is_active=True).exists()
        return Lambing.objects.filter(ewe=animal, is_active=True).exists()

    def _latest_completed_lambing_as_mother(self, animal):
        queryset = Lambing.objects.filter(is_active=False)
        tag_number = animal.tag.tag_number if getattr(animal, "tag", None) else ""
        relation_filter = Q()
        if isinstance(animal, Sheep):
            relation_filter |= Q(sheep=animal)
        else:
            relation_filter |= Q(ewe=animal)
        if tag_number:
            relation_filter |= Q(sheep__tag__tag_number__iexact=tag_number)
            relation_filter |= Q(ewe__tag__tag_number__iexact=tag_number)
            relation_filter |= Q(mother_tag_text__iexact=tag_number)
        queryset = queryset.filter(relation_filter)

        lambings = list(queryset)
        if not lambings:
            return None

        return max(
            lambings,
            key=lambda lambing: (
                lambing.actual_lambing_date
                or lambing.start_date
                or lambing.planned_lambing_date
                or date.min,
                lambing.id or 0,
            ),
        )

    @staticmethod
    def _model_label(model):
        labels = {
            Maker: "Баран-производитель",
            Ram: "Баранчик",
            Ewe: "Ярка",
            Sheep: "Овцематка",
        }
        return labels.get(model, model.__name__)
