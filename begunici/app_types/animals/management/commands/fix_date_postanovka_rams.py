from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from begunici.app_types.animals.models import Lambing, LambingGroup


def _animal_tag(animal):
    if not animal:
        return "-"
    tag = getattr(animal, "tag", None)
    if not tag:
        return "-"
    return tag.tag_number


def _mother_label(lambing):
    if lambing.sheep_id:
        return f"овцематка {_animal_tag(lambing.sheep)}"
    if lambing.ewe_id:
        return f"ярка {_animal_tag(lambing.ewe)}"
    if lambing.mother_tag_text:
        return f"текстовая мать {lambing.mother_tag_text}"
    return "без матери"


def _father_label(lambing):
    if lambing.maker_id:
        return f"баран-производитель {_animal_tag(lambing.maker)}"
    if lambing.ram_id:
        return f"баранчик {_animal_tag(lambing.ram)}"
    return "без отца"


class Command(BaseCommand):
    help = (
        "Создает закрытые группы случек для старых окотов без source_group: "
        "дата постановки = дата снятия барана - N дней."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Сохранить изменения. Без этого флага команда работает как dry-run.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Явно включить режим просмотра без сохранения.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=60,
            help="Сколько дней вычитать из даты снятия барана (по умолчанию: 60).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Ограничить количество обрабатываемых окотов.",
        )

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("Нельзя одновременно указывать --apply и --dry-run.")

        days = options["days"]
        if days <= 0:
            raise CommandError("--days должен быть положительным числом.")

        dry_run = not options["apply"]
        limit = options.get("limit")
        if limit is not None and limit <= 0:
            raise CommandError("--limit должен быть положительным числом.")

        queryset = (
            Lambing.objects.filter(source_group__isnull=True)
            .select_related("sheep__tag", "ewe__tag", "maker__tag", "ram__tag")
            .order_by("id")
        )

        total_candidates = queryset.count()
        if limit:
            queryset = queryset[:limit]

        self.stdout.write(
            f"Найдено окотов без группы: {total_candidates}. "
            f"К обработке сейчас: {len(queryset)}."
        )
        mode_label = "DRY-RUN: изменения не будут сохранены" if dry_run else "APPLY: изменения будут сохранены"
        self.stdout.write(self.style.WARNING(mode_label))

        stats = {
            "created": 0,
            "skipped_no_start_date": 0,
            "skipped_no_father": 0,
            "skipped_no_db_mother": 0,
        }
        planned_changes = []

        for lambing in queryset:
            if not lambing.start_date:
                stats["skipped_no_start_date"] += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Пропуск окота #{lambing.id}: нет даты снятия барана/start_date."
                    )
                )
                continue

            if not lambing.maker_id and not lambing.ram_id:
                stats["skipped_no_father"] += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Пропуск окота #{lambing.id}: нет отца ({_mother_label(lambing)})."
                    )
                )
                continue

            if not lambing.sheep_id and not lambing.ewe_id:
                stats["skipped_no_db_mother"] += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Пропуск окота #{lambing.id}: мать не привязана к животному в БД "
                        f"({_mother_label(lambing)})."
                    )
                )
                continue

            placement_date = lambing.start_date - timedelta(days=days)
            planned_changes.append((lambing, placement_date))
            stats["created"] += 1
            self.stdout.write(
                "Окот #{id}: {mother}; {father}; постановка {placement}; снятие {removal}".format(
                    id=lambing.id,
                    mother=_mother_label(lambing),
                    father=_father_label(lambing),
                    placement=placement_date.strftime("%d.%m.%Y"),
                    removal=lambing.start_date.strftime("%d.%m.%Y"),
                )
            )

        if dry_run:
            self._write_summary(stats, dry_run=True)
            self.stdout.write(self.style.WARNING("DRY-RUN завершен. Для сохранения запустите с --apply."))
            return

        with transaction.atomic():
            for lambing, placement_date in planned_changes:
                group = LambingGroup.objects.create(
                    maker=lambing.maker,
                    ram=lambing.ram,
                    placement_date=placement_date,
                    removal_date=lambing.start_date,
                    is_active=False,
                    note=(
                        "Автоматически создано для исторического окота "
                        f"#{lambing.id}: дата постановки рассчитана как дата снятия - {days} дней."
                    ),
                )

                if lambing.sheep_id:
                    group.sheep.add(lambing.sheep)
                elif lambing.ewe_id:
                    group.ewes.add(lambing.ewe)

                lambing.source_group = group
                lambing.save(update_fields=["source_group"])

        self._write_summary(stats, dry_run=False)
        self.stdout.write(self.style.SUCCESS("Готово. Исторические группы созданы и привязаны к окотам."))

    def _write_summary(self, stats, dry_run):
        created_label = "Планируется создать групп" if dry_run else "Создано групп"
        self.stdout.write("")
        self.stdout.write("Итог:")
        self.stdout.write(f"  {created_label}: {stats['created']}")
        self.stdout.write(f"  Пропущено без даты снятия барана: {stats['skipped_no_start_date']}")
        self.stdout.write(f"  Пропущено без отца: {stats['skipped_no_father']}")
        self.stdout.write(f"  Пропущено без матери-животного в БД: {stats['skipped_no_db_mother']}")
