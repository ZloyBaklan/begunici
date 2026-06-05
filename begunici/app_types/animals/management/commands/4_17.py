from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from begunici.app_types.animals.models import Ewe, Maker, Ram, Sheep
from begunici.app_types.veterinary.vet_models import Place, PlaceMovement


TARGET_PLACE_NAME = "Овчарня 4 Отсек 17"


class Command(BaseCommand):
    help = "Переводит всех активных животных в овчарню 4, отсек 17."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, какие изменения будут внесены, без сохранения.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        target_place = (
            Place.objects.filter(sheepfold__iexact=TARGET_PLACE_NAME).first()
            or Place.objects.filter(
                Q(sheepfold__icontains="Овчарня 4") & Q(sheepfold__icontains="Отсек 17")
            ).first()
        )
        if target_place is None:
            raise CommandError(f"Место '{TARGET_PLACE_NAME}' не найдено.")

        models = [
            ("Бараны-Производители", Maker),
            ("Баранчики", Ram),
            ("Ярки", Ewe),
            ("Овцематки", Sheep),
        ]

        stats = {
            "active_total": 0,
            "already_in_place": 0,
            "will_move": 0,
            "moved": 0,
        }
        per_model = []

        for label, model in models:
            active_qs = model.objects.filter(is_archived=False).select_related("tag", "place")
            active_count = active_qs.count()
            same_place_count = active_qs.filter(place=target_place).count()
            to_move_count = active_count - same_place_count

            stats["active_total"] += active_count
            stats["already_in_place"] += same_place_count
            stats["will_move"] += to_move_count

            per_model.append((label, active_count, same_place_count, to_move_count))

        self.stdout.write(f"Целевое место: {target_place.sheepfold}")
        self.stdout.write(f"Активных животных всего: {stats['active_total']}")
        self.stdout.write(f"Уже в целевом месте: {stats['already_in_place']}")
        self.stdout.write(f"К переводу: {stats['will_move']}")
        self.stdout.write("")
        for label, active_count, same_place_count, to_move_count in per_model:
            self.stdout.write(
                f"{label}: активных {active_count}, уже в месте {same_place_count}, к переводу {to_move_count}"
            )

        if stats["will_move"] == 0:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Изменять нечего."))
            return

        if dry_run:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("DRY-RUN: изменения не применены."))
            return

        with transaction.atomic():
            for _, model in models:
                animals = model.objects.filter(is_archived=False).exclude(place=target_place).select_related(
                    "tag", "place"
                )
                for animal in animals:
                    old_place = animal.place
                    animal.place = target_place
                    animal.save(update_fields=["place"])

                    PlaceMovement.objects.create(
                        tag=animal.tag,
                        old_place=old_place,
                        new_place=target_place,
                    )
                    stats["moved"] += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Готово. Переведено животных: {stats['moved']}"))
