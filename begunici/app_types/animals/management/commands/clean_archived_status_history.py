from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from begunici.app_types.veterinary.vet_models import StatusHistory

from ...models import ARCHIVE_STATUS_NAMES, Ewe, Maker, Ram, Sheep


class Command(BaseCommand):
    help = (
        "Исправляет порядок истории статусов у архивных животных: не удаляет "
        "записи, а переносит время текущей архивной записи позже последнего "
        "события в StatusHistory."
    )

    MODELS = (
        ("Овцематка", Sheep),
        ("Ярка", Ewe),
        ("Баранчик", Ram),
        ("Баран-производитель", Maker),
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать изменения без сохранения.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Применить изменения.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        apply_changes = options["apply"]

        if dry_run and apply_changes:
            self.stderr.write(self.style.ERROR("Нельзя одновременно указывать --dry-run и --apply."))
            return
        if not dry_run and not apply_changes:
            dry_run = True

        self.checked = 0
        self.fixed = 0
        self.unchanged = 0
        self.missing_archive_history = []

        mode_message = (
            "DRY-RUN: изменения не будут сохранены"
            if dry_run
            else "Режим применения: изменения будут сохранены"
        )
        self.stdout.write(self.style.WARNING(mode_message))

        with transaction.atomic():
            for label, model in self.MODELS:
                self._process_model(label, model, dry_run=dry_run)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Итог:"))
        self.stdout.write(f"  Проверено архивных животных: {self.checked}")
        self.stdout.write(f"  Архивных записей будет исправлено/исправлено: {self.fixed}")
        self.stdout.write(f"  Без изменений: {self.unchanged}")

        if self.missing_archive_history:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Архивные животные без записи текущего архивного статуса в истории:"))
            for item in self.missing_archive_history:
                self.stdout.write(f"  - {item}")

    def _process_model(self, label, model, dry_run):
        animals = (
            model.objects.select_related("tag", "animal_status")
            .filter(is_archived=True, animal_status__status_type__in=ARCHIVE_STATUS_NAMES)
            .order_by("tag__tag_number")
        )

        self.stdout.write("")
        self.stdout.write(f"{label}: {animals.count()} архивных записей")

        for animal in animals:
            self.checked += 1
            tag = animal.tag.tag_number if animal.tag else f"id={animal.id}"
            current_status = animal.animal_status.status_type if animal.animal_status else ""

            histories = list(
                StatusHistory.objects.filter(tag=animal.tag)
                .select_related("new_status")
                .order_by("change_date", "id")
            )
            if not histories:
                self.unchanged += 1
                self.missing_archive_history.append(
                    f"{label} {tag}: история статусов пустая, текущий статус {current_status}"
                )
                continue

            current_archive_history = None
            for history in histories:
                history_status = history.new_status.status_type if history.new_status else ""
                if history_status == current_status:
                    current_archive_history = history

            if current_archive_history is None:
                self.unchanged += 1
                self.missing_archive_history.append(
                    f"{label} {tag}: не найдена запись '{current_status}'"
                )
                continue

            last_history = histories[-1]
            if last_history.pk == current_archive_history.pk:
                self.unchanged += 1
                continue

            active_after_archive = [
                history
                for history in histories
                if (
                    history.change_date >= current_archive_history.change_date
                    and history.pk != current_archive_history.pk
                    and (
                        not history.new_status
                        or history.new_status.status_type not in ARCHIVE_STATUS_NAMES
                    )
                )
            ]

            if not active_after_archive:
                self.unchanged += 1
                continue

            new_change_date = last_history.change_date + timedelta(seconds=1)
            old_change_date = current_archive_history.change_date
            self.fixed += 1

            self.stdout.write(
                f"  {label} {tag}: '{current_status}' "
                f"{old_change_date:%d.%m.%Y %H:%M:%S} -> {new_change_date:%d.%m.%Y %H:%M:%S}; "
                f"последнее событие было {last_history.change_date:%d.%m.%Y %H:%M:%S}"
            )

            if not dry_run:
                current_archive_history.change_date = new_change_date
                current_archive_history.save(update_fields=["change_date"])
