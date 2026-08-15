from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import router, transaction
from django.db.models.deletion import Collector

from begunici.app_types.animals.models import Ewe, Maker, Ram, Sheep
from begunici.app_types.veterinary.vet_models import PlaceMovement, StatusHistory


class Command(BaseCommand):
    help = (
        "Ищет дубли бирок среди всех типов животных. Команда ничего не меняет в базе."
    )

    animal_sources = (
        ("Баран-производитель", Maker),
        ("Баранчик", Ram),
        ("Ярка", Ewe),
        ("Овцематка", Sheep),
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="Показывать только дубли среди неархивных животных.",
        )
        parser.add_argument(
            "--with-clean-summary",
            action="store_true",
            help="В конце показать количество животных без дублей.",
        )
        parser.add_argument(
            "--clear_duble_tag",
            action="store_true",
            help=(
                "Для дублей с одним общим Tag id удалить архивные записи животных. "
                "Без --apply только показывает, что будет удалено."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Применить удаление для --clear_duble_tag.",
        )

    def handle(self, *args, **options):
        active_only = options["active_only"]
        with_clean_summary = options["with_clean_summary"]
        clear_duble_tag = options["clear_duble_tag"]
        apply_changes = options["apply"]

        if apply_changes and not clear_duble_tag:
            raise CommandError("--apply можно использовать только вместе с --clear_duble_tag.")
        if clear_duble_tag and active_only:
            raise CommandError("--clear_duble_tag нельзя использовать вместе с --active-only.")

        groups = defaultdict(list)
        total_animals = 0

        for label, model in self.animal_sources:
            queryset = model.objects.select_related("tag", "animal_status", "place").all()
            if active_only:
                queryset = queryset.filter(is_archived=False)

            for animal in queryset:
                total_animals += 1
                tag_number = animal.tag.tag_number if animal.tag else ""
                normalized_tag = self._normalize_tag(tag_number)
                if not normalized_tag:
                    normalized_tag = f"__empty_tag__:{label}:{animal.pk}"

                groups[normalized_tag].append(
                    {
                        "label": label,
                        "model": model.__name__,
                        "model_class": model,
                        "id": animal.pk,
                        "tag_id": animal.tag_id,
                        "tag_number": tag_number or "-",
                        "status": (
                            animal.animal_status.status_type
                            if animal.animal_status
                            else "нет статуса"
                        ),
                        "place": animal.place.sheepfold if animal.place else "нет места",
                        "birth_date": (
                            animal.birth_date.strftime("%d.%m.%Y")
                            if animal.birth_date
                            else "-"
                        ),
                        "is_archived": animal.is_archived,
                    }
                )

        duplicate_groups = {
            tag: records
            for tag, records in groups.items()
            if len(records) > 1
        }

        self.stdout.write(
            "Проверено животных: "
            f"{total_animals}"
            + (" (только активные)" if active_only else "")
        )

        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS("Дубли бирок не найдены."))
            return

        duplicate_records_count = sum(len(records) for records in duplicate_groups.values())
        self.stdout.write(
            self.style.WARNING(
                f"Найдено групп дублей: {len(duplicate_groups)}; "
                f"животных в дублях: {duplicate_records_count}"
            )
        )

        for normalized_tag in sorted(duplicate_groups.keys()):
            records = sorted(
                duplicate_groups[normalized_tag],
                key=lambda item: (item["tag_number"].lower(), item["label"], item["id"]),
            )
            display_tags = sorted({record["tag_number"] for record in records})
            tag_ids = sorted({record["tag_id"] for record in records if record["tag_id"]})
            status_history_count = (
                StatusHistory.objects.filter(tag_id__in=tag_ids).count()
                if tag_ids
                else 0
            )
            place_history_count = (
                PlaceMovement.objects.filter(tag_id__in=tag_ids).count()
                if tag_ids
                else 0
            )

            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    f"Бирка: {', '.join(display_tags)} | записей: {len(records)}"
                )
            )

            if len(tag_ids) == 1:
                self.stdout.write(
                    self.style.ERROR(
                        f"  Общий Tag id: {tag_ids[0]}. История статусов/перемещений общая."
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "  Разные Tag id: "
                        + (", ".join(str(tag_id) for tag_id in tag_ids) or "-")
                        + ". Похоже на дубль номера/регистра."
                    )
                )

            self.stdout.write(f"  Записей истории статусов по этим Tag: {status_history_count}")
            self.stdout.write(f"  Записей истории перемещений по этим Tag: {place_history_count}")

            for record in records:
                archive_label = "архив" if record["is_archived"] else "активное"
                self.stdout.write(
                    "  - "
                    f"{record['label']} | id={record['id']} | "
                    f"tag_id={record['tag_id']} | {archive_label} | "
                    f"статус: {record['status']} | "
                    f"место: {record['place']} | "
                    f"дата рождения: {record['birth_date']}"
                )

        if clear_duble_tag:
            self._clear_archived_same_tag_duplicates(
                duplicate_groups,
                apply_changes=apply_changes,
            )

        if with_clean_summary:
            clean_count = sum(
                len(records)
                for records in groups.values()
                if len(records) == 1
            )
            self.stdout.write("")
            self.stdout.write(f"Животных без дублей: {clean_count}")

    @staticmethod
    def _normalize_tag(value):
        return (value or "").strip().lower()

    def _clear_archived_same_tag_duplicates(self, duplicate_groups, apply_changes):
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "Очистка дублей с общим Tag id "
                + ("(ПРИМЕНЕНИЕ)" if apply_changes else "(dry-run, без изменений)")
            )
        )

        planned_deletions = []
        skipped = []
        tag_ids_to_cleanup = set()

        for normalized_tag in sorted(duplicate_groups.keys()):
            records = duplicate_groups[normalized_tag]
            tag_ids = {record["tag_id"] for record in records if record["tag_id"]}
            display_tags = sorted({record["tag_number"] for record in records})
            display_tag = ", ".join(display_tags)

            if len(tag_ids) != 1:
                skipped.append(
                    f"{display_tag}: разные Tag id, это не общий Tag. Нужна ручная проверка."
                )
                continue

            active_records = [record for record in records if not record["is_archived"]]
            archived_records = [record for record in records if record["is_archived"]]

            if len(active_records) != 1:
                skipped.append(
                    f"{display_tag}: активных записей {len(active_records)}. "
                    "Автоматически безопасно выбрать, кого оставить, нельзя."
                )
                continue

            if not archived_records:
                skipped.append(
                    f"{display_tag}: архивных записей для удаления нет."
                )
                continue

            kept_record = active_records[0]
            for record in archived_records:
                unsafe_reason = self._get_unsafe_delete_reason(record)
                if unsafe_reason:
                    skipped.append(f"{display_tag}: {unsafe_reason}")
                    continue
                planned_deletions.append((display_tag, kept_record, record))
                tag_ids_to_cleanup.add(next(iter(tag_ids)))

        if not planned_deletions:
            self.stdout.write(self.style.WARNING("Нет записей, подходящих для автоочистки."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Будет удалено архивных животных: {len(planned_deletions)}"
                )
            )
            for display_tag, kept_record, record in planned_deletions:
                self.stdout.write(
                    "  - удалить: "
                    f"{record['label']} id={record['id']} ({record['status']}, архив); "
                    f"оставить: {kept_record['label']} id={kept_record['id']} "
                    f"({kept_record['status']}, активное); бирка: {display_tag}"
                )

        if skipped:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Пропущено:"))
            for message in skipped:
                self.stdout.write(f"  - {message}")

        if tag_ids_to_cleanup and not apply_changes:
            self._cleanup_duplicate_tag_histories(
                tag_ids_to_cleanup,
                apply_changes=apply_changes,
            )

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Изменения не применены. Для удаления добавьте --apply."
                )
            )
            return

        if not planned_deletions:
            return

        deleted_count = 0
        with transaction.atomic():
            for _, _, record in planned_deletions:
                model = record["model_class"]
                deleted, _ = model.objects.filter(pk=record["id"]).delete()
                if deleted:
                    deleted_count += 1
            if tag_ids_to_cleanup:
                self._cleanup_duplicate_tag_histories(
                    tag_ids_to_cleanup,
                    apply_changes=True,
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Удалено архивных животных: {deleted_count}")
        )
        self.stdout.write(
            self.style.WARNING(
                "Важно: у очищенных общих Tag оставлена только последняя запись истории статусов "
                "и последняя запись истории перемещений. Записи веса, ветобработок и актов не удалялись."
            )
        )

    def _cleanup_duplicate_tag_histories(self, tag_ids, apply_changes):
        status_delete_ids = []
        place_delete_ids = []

        for tag_id in sorted(tag_ids):
            status_keep = (
                StatusHistory.objects.filter(tag_id=tag_id)
                .order_by("-change_date", "-id")
                .first()
            )
            if status_keep:
                status_delete_ids.extend(
                    StatusHistory.objects.filter(tag_id=tag_id)
                    .exclude(pk=status_keep.pk)
                    .values_list("pk", flat=True)
                )

            place_keep = (
                PlaceMovement.objects.filter(tag_id=tag_id)
                .order_by("-created_at", "-id")
                .first()
            )
            if place_keep:
                place_delete_ids.extend(
                    PlaceMovement.objects.filter(tag_id=tag_id)
                    .exclude(pk=place_keep.pk)
                    .values_list("pk", flat=True)
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "Очистка истории общих Tag: "
                f"статусов к удалению {len(status_delete_ids)}, "
                f"перемещений к удалению {len(place_delete_ids)}"
            )
        )

        if not apply_changes:
            return

        deleted_statuses = 0
        deleted_places = 0
        if status_delete_ids:
            deleted_statuses, _ = StatusHistory.objects.filter(pk__in=status_delete_ids).delete()
        if place_delete_ids:
            deleted_places, _ = PlaceMovement.objects.filter(pk__in=place_delete_ids).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Удалено старых записей истории: статусы {deleted_statuses}, "
                f"перемещения {deleted_places}"
            )
        )

    def _get_unsafe_delete_reason(self, record):
        model = record["model_class"]
        animal = model.objects.filter(pk=record["id"]).first()
        if animal is None:
            return (
                f"{record['label']} id={record['id']} уже не найден. "
                "Возможно, запись была удалена раньше."
            )

        collector = Collector(using=router.db_for_write(model, instance=animal))
        collector.collect([animal])

        unsafe_parts = []
        for related_model, objects in collector.data.items():
            if related_model is model:
                continue
            unsafe_parts.append(f"{related_model._meta.label}: {len(objects)}")

        for queryset in collector.fast_deletes:
            related_model = queryset.model
            # Автосозданные M2M-таблицы содержат только связь удаляемого животного
            # с записью веса/ветобработки. Это безопасно: сами общие записи не удаляются.
            if related_model._meta.auto_created:
                continue
            count = queryset.count()
            if count:
                unsafe_parts.append(f"{related_model._meta.label}: {count}")

        if not unsafe_parts:
            return None

        return (
            f"{record['label']} id={record['id']} не удаляется автоматически, "
            "потому что вместе с ним Django удалит связанные записи: "
            + "; ".join(unsafe_parts)
        )
