from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from begunici.app_types.animals.models import Ewe, Maker, Ram, Sheep
from begunici.app_types.veterinary.vet_models import Status


class Command(BaseCommand):
    help = "Replace status 'Холостой' with 'Откорм' for all animal types."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many records will be changed without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        holostoy_status = Status.objects.filter(status_type__iexact="Холостой").first()
        if not holostoy_status:
            raise CommandError("Status 'Холостой' not found.")

        otkorm_status = Status.objects.filter(status_type__iexact="Откорм").first()
        if not otkorm_status:
            raise CommandError("Status 'Откорм' not found.")

        models = [
            ("Бараны-Производители", Maker),
            ("Баранчики", Ram),
            ("Ярки", Ewe),
            ("Овцематки", Sheep),
        ]

        total_to_update = 0
        per_model_counts = []
        for label, model in models:
            count = model.objects.filter(animal_status=holostoy_status).count()
            total_to_update += count
            per_model_counts.append((label, count))

        self.stdout.write(f"Найдено животных со статусом 'Холостой': {total_to_update}")
        for label, count in per_model_counts:
            self.stdout.write(f"  {label}: {count}")

        if total_to_update == 0:
            self.stdout.write(self.style.WARNING("Изменять нечего."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: изменения не сохранены."))
            return

        updated = 0
        with transaction.atomic():
            for _, model in models:
                animals = model.objects.filter(animal_status=holostoy_status).select_related("tag")
                for animal in animals:
                    animal.animal_status = otkorm_status
                    animal.save()
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f"Готово. Обновлено животных: {updated}"))

