from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from begunici.app_types.animals.models import Ewe, Lambing, Maker, Ram, Sheep


def _normalize_tag(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _clean_tag(value):
    if value is None:
        return ""
    return str(value).strip()


@dataclass
class ChildRef:
    model_name: str
    instance: object
    mother_norm: str
    tag_number: str
    sex: str  # "female" | "male"

    @property
    def key(self):
        return f"{self.model_name}:{self.instance.pk}"


class Command(BaseCommand):
    help = (
        "Синхронизирует завершённые окоты с детьми по бирке матери и дате рождения. "
        "Обновляет даты рождения детей на фактическую дату окота, число живых ягнят и, при необходимости, "
        "количество мёртвых ягнят."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--window-days",
            type=int,
            default=1,
            help="Основное окно поиска детей вокруг actual_lambing_date в днях (по умолчанию: 1).",
        )
        parser.add_argument(
            "--collision-min-days",
            type=int,
            default=5,
            help="Минимальная абсолютная дельта в днях для логирования коллизий (по умолчанию: 5).",
        )
        parser.add_argument(
            "--collision-max-days",
            type=int,
            default=50,
            help="Максимальная абсолютная дельта в днях для логирования коллизий (по умолчанию: 50).",
        )
        parser.add_argument(
            "--mother-tag",
            type=str,
            help="Обработать только окоты этой матери (без учёта регистра).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Ограничить количество обрабатываемых окотов.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать предлагаемые изменения без сохранения.",
        )

    def _collect_children(self, mothers_set, date_from, date_to):
        by_mother = defaultdict(list)

        def add_children(model, model_name, sex):
            queryset = (
                model.objects.filter(
                    birth_date__isnull=False,
                    birth_date__gte=date_from,
                    birth_date__lte=date_to,
                    mother__isnull=False,
                )
                .select_related("tag")
            )
            for child in queryset:
                mother_norm = _normalize_tag(child.mother)
                if not mother_norm or mother_norm not in mothers_set:
                    continue
                tag_number = _clean_tag(getattr(child.tag, "tag_number", ""))
                by_mother[mother_norm].append(
                    ChildRef(
                        model_name=model_name,
                        instance=child,
                        mother_norm=mother_norm,
                        tag_number=tag_number,
                        sex=sex,
                    )
                )

        add_children(Ewe, "Ewe", "female")
        add_children(Sheep, "Sheep", "female")
        add_children(Ram, "Ram", "male")
        add_children(Maker, "Maker", "male")

        return by_mother

    @staticmethod
    def _child_sort_key(child_ref, actual_date):
        delta = abs((child_ref.instance.birth_date - actual_date).days)
        return (
            delta,
            child_ref.instance.birth_date,
            child_ref.tag_number.lower(),
            child_ref.model_name,
            child_ref.instance.pk,
        )

    @staticmethod
    def _format_collision_child(child_ref, actual_date):
        model_titles = {
            "Ewe": "Ярка",
            "Sheep": "Овцематка",
            "Ram": "Баранчик",
            "Maker": "Баран-Производитель",
        }
        delta = (child_ref.instance.birth_date - actual_date).days
        sign = "+" if delta >= 0 else ""
        tag = child_ref.tag_number or f"ID={child_ref.instance.pk}"
        model_title = model_titles.get(child_ref.model_name, child_ref.model_name)
        return (
            f"{tag} [{model_title}] "
            f"дата рождения={child_ref.instance.birth_date} (дельта {sign}{delta})"
        )

    def handle(self, *args, **options):
        window_days = options["window_days"]
        collision_min_days = options["collision_min_days"]
        collision_max_days = options["collision_max_days"]
        dry_run = options["dry_run"]
        mother_tag_filter = _normalize_tag(options.get("mother_tag"))
        limit = options.get("limit")

        if window_days < 0:
            self.stdout.write(self.style.ERROR("--window-days не может быть отрицательным."))
            return
        if collision_min_days < 0:
            self.stdout.write(self.style.ERROR("--collision-min-days не может быть отрицательным."))
            return
        if collision_max_days < collision_min_days:
            self.stdout.write(
                self.style.ERROR("--collision-max-days должен быть >= --collision-min-days.")
            )
            return
        if limit is not None and limit <= 0:
            self.stdout.write(self.style.ERROR("--limit должен быть положительным целым числом."))
            return

        lambings_qs = (
            Lambing.objects.filter(is_active=False, actual_lambing_date__isnull=False)
            .exclude(completion_type=Lambing.COMPLETION_EARLY_FAILURE)
            .select_related("sheep__tag", "ewe__tag")
            .order_by("-actual_lambing_date", "-id")
        )
        lambings = list(lambings_qs)
        if not lambings:
            self.stdout.write(self.style.WARNING("Завершённые окоты не найдены."))
            return

        if mother_tag_filter:
            lambings = [
                lambing
                for lambing in lambings
                if _normalize_tag(lambing.get_mother_tag()) == mother_tag_filter
            ]
        if limit:
            lambings = lambings[:limit]

        if not lambings:
            self.stdout.write(self.style.WARNING("Нет окотов, подходящих под заданные фильтры."))
            return

        min_actual_date = min(l.actual_lambing_date for l in lambings)
        max_actual_date = max(l.actual_lambing_date for l in lambings)
        scan_span = max(window_days, collision_max_days)
        date_from = min_actual_date - timedelta(days=scan_span)
        date_to = max_actual_date + timedelta(days=scan_span)

        mothers_set = {
            _normalize_tag(lambing.get_mother_tag())
            for lambing in lambings
            if _normalize_tag(lambing.get_mother_tag())
        }
        children_by_mother = self._collect_children(mothers_set, date_from, date_to)

        stats = {
            "processed": 0,
            "no_mother": 0,
            "no_children_in_window": 0,
            "unchanged": 0,
            "updated": 0,
            "children_birth_date_changed": 0,
            "live_count_changed": 0,
            "dead_count_changed": 0,
            "collisions_lambings": 0,
            "collisions_children": 0,
        }
        changed_rows = []
        dead_changed_rows = []
        collision_rows = []
        used_children = set()

        optional_tag_fields = {
            "female": [
                "female_lamb_tags",
                "ewe_lamb_tags",
                "yarka_lamb_tags",
            ],
            "male": [
                "male_lamb_tags",
                "ram_lamb_tags",
                "baranchik_lamb_tags",
            ],
            "common": [
                "lamb_tags",
                "children_tags",
            ],
        }

        with transaction.atomic():
            for lambing in lambings:
                stats["processed"] += 1

                mother_norm = _normalize_tag(lambing.get_mother_tag())
                if not mother_norm:
                    stats["no_mother"] += 1
                    continue

                actual_date = lambing.actual_lambing_date
                mother_children = children_by_mother.get(mother_norm, [])
                if not mother_children:
                    stats["no_children_in_window"] += 1
                    continue

                available_children = [
                    c for c in mother_children if c.key not in used_children
                ]

                matched_children = []
                for child_ref in available_children:
                    delta_abs = abs((child_ref.instance.birth_date - actual_date).days)
                    if delta_abs <= window_days:
                        matched_children.append(child_ref)

                if not matched_children:
                    stats["no_children_in_window"] += 1
                    continue

                matched_children.sort(
                    key=lambda c: self._child_sort_key(c, actual_date)
                )

                collision_children = []
                for child_ref in available_children:
                    delta_abs = abs((child_ref.instance.birth_date - actual_date).days)
                    if collision_min_days <= delta_abs <= collision_max_days:
                        collision_children.append(child_ref)

                if collision_children:
                    stats["collisions_lambings"] += 1
                    stats["collisions_children"] += len(collision_children)
                    collision_rows.append(
                        {
                            "id": lambing.id,
                            "mother": lambing.get_mother_tag() or "-",
                            "actual_date": actual_date,
                            "items": [
                                self._format_collision_child(c, actual_date)
                                for c in sorted(
                                    collision_children,
                                    key=lambda c: (
                                        abs((c.instance.birth_date - actual_date).days),
                                        c.instance.birth_date,
                                        c.tag_number.lower(),
                                    ),
                                )
                            ],
                        }
                    )

                female_tags = sorted(
                    [c.tag_number for c in matched_children if c.sex == "female" and c.tag_number],
                    key=lambda x: x.lower(),
                )
                male_tags = sorted(
                    [c.tag_number for c in matched_children if c.sex == "male" and c.tag_number],
                    key=lambda x: x.lower(),
                )

                optional_updates = {}
                for field_name in optional_tag_fields["female"]:
                    if hasattr(lambing, field_name):
                        optional_updates[field_name] = "; ".join(female_tags)
                        break
                for field_name in optional_tag_fields["male"]:
                    if hasattr(lambing, field_name):
                        optional_updates[field_name] = "; ".join(male_tags)
                        break
                for field_name in optional_tag_fields["common"]:
                    if hasattr(lambing, field_name):
                        optional_updates[field_name] = "; ".join(female_tags + male_tags)
                        break

                old_live = lambing.number_of_lambs or 0
                old_dead = lambing.dead_lambs_count or 0
                new_live = len(matched_children)
                missing_live = max(0, old_live - new_live)
                new_dead = max(old_dead, missing_live)

                live_changed = old_live != new_live
                dead_changed = old_dead != new_dead
                optional_changed = any(
                    getattr(lambing, field_name) != field_value
                    for field_name, field_value in optional_updates.items()
                )

                child_date_updates = [
                    child_ref
                    for child_ref in matched_children
                    if child_ref.instance.birth_date != actual_date
                ]
                child_dates_changed = len(child_date_updates) > 0

                for child_ref in matched_children:
                    used_children.add(child_ref.key)

                if not live_changed and not dead_changed and not optional_changed and not child_dates_changed:
                    stats["unchanged"] += 1
                    continue

                for child_ref in child_date_updates:
                    child_ref.instance.birth_date = actual_date
                    if not dry_run:
                        child_ref.instance.save(update_fields=["birth_date"])

                lambing.number_of_lambs = new_live
                lambing.dead_lambs_count = new_dead
                for field_name, field_value in optional_updates.items():
                    setattr(lambing, field_name, field_value)
                if not dry_run:
                    update_fields = ["number_of_lambs", "dead_lambs_count"]
                    update_fields.extend(optional_updates.keys())
                    lambing.save(update_fields=update_fields)

                if child_dates_changed:
                    stats["children_birth_date_changed"] += len(child_date_updates)
                if live_changed:
                    stats["live_count_changed"] += 1
                if dead_changed:
                    stats["dead_count_changed"] += 1
                    dead_changed_rows.append(
                        {
                            "id": lambing.id,
                            "mother": lambing.get_mother_tag() or "-",
                            "actual_date": actual_date,
                            "old_dead": old_dead,
                            "new_dead": new_dead,
                            "old_live": old_live,
                            "new_live": new_live,
                        }
                    )
                stats["updated"] += 1

                changed_rows.append(
                    {
                        "id": lambing.id,
                        "mother": lambing.get_mother_tag() or "-",
                        "actual_date": actual_date,
                        "old_live": old_live,
                        "new_live": new_live,
                        "old_dead": old_dead,
                        "new_dead": new_dead,
                        "children_dates_changed": len(child_date_updates),
                    }
                )

            if dry_run:
                transaction.set_rollback(True)

        mode = "ПРОБНЫЙ ЗАПУСК" if dry_run else "ПРИМЕНЕНО"
        self.stdout.write(self.style.SUCCESS(f"[{mode}] Синхронизация окотов завершена"))
        self.stdout.write(f"Обработано окотов: {stats['processed']}")
        self.stdout.write(f"Обновлено: {stats['updated']}")
        self.stdout.write(
            f"  - Изменено дат рождения детей: {stats['children_birth_date_changed']}"
        )
        self.stdout.write(f"  - Изменено количество живых ягнят: {stats['live_count_changed']}")
        self.stdout.write(
            f"  - Изменено количество мёртвых ягнят: {stats['dead_count_changed']}"
        )
        self.stdout.write(f"Без изменений: {stats['unchanged']}")
        self.stdout.write(f"Пропущено (нет матери): {stats['no_mother']}")
        self.stdout.write(f"Пропущено (нет детей в основном окне): {stats['no_children_in_window']}")
        self.stdout.write(
            f"Коллизии (|дельта| в диапазоне {collision_min_days}..{collision_max_days}): "
            f"окотов={stats['collisions_lambings']}, детей={stats['collisions_children']}"
        )

        if changed_rows:
            self.stdout.write("")
            self.stdout.write("Первые 20 обновлений:")
            for row in changed_rows[:20]:
                self.stdout.write(
                    f"  Окот #{row['id']} | мать {row['mother']} | "
                    f"факт. дата {row['actual_date']} | "
                    f"живые {row['old_live']} -> {row['new_live']} | "
                    f"мёртвые {row['old_dead']} -> {row['new_dead']} | "
                    f"изменено дат у детей: {row['children_dates_changed']}"
                )
            if len(changed_rows) > 20:
                self.stdout.write(f"  ... и ещё {len(changed_rows) - 20} обновлений")

        if dead_changed_rows:
            self.stdout.write("")
            self.stdout.write("Изменения количества мёртвых (первые 20):")
            for row in dead_changed_rows[:20]:
                self.stdout.write(
                    f"  Окот #{row['id']} | мать {row['mother']} | "
                    f"факт. дата {row['actual_date']} | "
                    f"мёртвые {row['old_dead']} -> {row['new_dead']} | "
                    f"живые {row['old_live']} -> {row['new_live']}"
                )
            if len(dead_changed_rows) > 20:
                self.stdout.write(
                    f"  ... и ещё {len(dead_changed_rows) - 20} изменений по мёртвым"
                )

        if collision_rows:
            self.stdout.write("")
            self.stdout.write("Подсказки по коллизиям (первые 20 окотов):")
            for row in collision_rows[:20]:
                self.stdout.write(
                    f"  Окот #{row['id']} | мать {row['mother']} | факт. дата {row['actual_date']}"
                )
                for item in row["items"][:10]:
                    self.stdout.write(f"    - {item}")
                if len(row["items"]) > 10:
                    self.stdout.write(f"    - ... и ещё {len(row['items']) - 10}")
            if len(collision_rows) > 20:
                self.stdout.write(f"  ... и ещё {len(collision_rows) - 20} окотов")
