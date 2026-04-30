from django.core.management.base import BaseCommand
from django.db import transaction

from begunici.app_types.veterinary.vet_models import Veterinary, VeterinaryCare


class Command(BaseCommand):
    help = (
        "Миграция структуры ветобработок: все записи VeterinaryCare переводятся "
        "в тип 'Вакцинация' и класс 'Иммунизация' с безопасным слиянием дублей."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать изменения без записи в базу.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        target_type = VeterinaryCare.TYPE_VACCINATION
        target_class = VeterinaryCare.CLASS_IMMUNIZATION

        cares = list(
            VeterinaryCare.objects.all().order_by("id").only(
                "id", "care_type", "care_name", "medication", "purpose"
            )
        )
        if not cares:
            self.stdout.write(self.style.WARNING("Ветобработки не найдены."))
            return

        kept_by_key = {}
        stats = {
            "total_cares": len(cares),
            "updated_cares": 0,
            "merged_cares": 0,
            "relinked_records": 0,
        }

        with transaction.atomic():
            for care in cares:
                # После миграции ключ уникальности должен учитываться уже в новой структуре.
                key = (target_type, target_class, care.medication, care.purpose)
                keeper_id = kept_by_key.get(key)

                if keeper_id is None:
                    kept_by_key[key] = care.id
                    if care.care_type != target_type or care.care_name != target_class:
                        stats["updated_cares"] += 1
                        if not dry_run:
                            VeterinaryCare.objects.filter(id=care.id).update(
                                care_type=target_type,
                                care_name=target_class,
                            )
                    continue

                refs_qs = Veterinary.objects.filter(veterinary_care_id=care.id)
                refs_count = refs_qs.count()
                if refs_count:
                    stats["relinked_records"] += refs_count
                    if not dry_run:
                        refs_qs.update(veterinary_care_id=keeper_id)

                stats["merged_cares"] += 1
                if not dry_run:
                    VeterinaryCare.objects.filter(id=care.id).delete()

            if dry_run:
                transaction.set_rollback(True)

        mode = "DRY-RUN" if dry_run else "DONE"
        self.stdout.write(self.style.SUCCESS(f"[{mode}] Миграция структуры ветобработок завершена"))
        self.stdout.write(f"Всего ветобработок: {stats['total_cares']}")
        self.stdout.write(f"Обновлено type/class: {stats['updated_cares']}")
        self.stdout.write(f"Слито дублей VeterinaryCare: {stats['merged_cares']}")
        self.stdout.write(f"Переназначено применённых записей Veterinary: {stats['relinked_records']}")
