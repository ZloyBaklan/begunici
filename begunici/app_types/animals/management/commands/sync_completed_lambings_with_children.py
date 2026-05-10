from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from begunici.app_types.animals.models import Ewe, Lambing, Ram, Sheep


def _normalize_tag(value):
    if value is None:
        return ""
    return str(value).strip().lower()


class Command(BaseCommand):
    help = (
        "Sync completed lambings with real children by mother tag and birth date "
        "(default window: +/- 1 day). Updates actual_lambing_date and number_of_lambs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--window-days",
            type=int,
            default=5,
            help="Date window in days around actual_lambing_date (default: 1).",
        )
        parser.add_argument(
            "--mother-tag",
            type=str,
            help="Process only lambings for this mother tag (case-insensitive).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit number of lambings to process.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show proposed changes without saving them.",
        )

    def handle(self, *args, **options):
        window_days = options["window_days"]
        dry_run = options["dry_run"]
        mother_tag_filter = _normalize_tag(options.get("mother_tag"))
        limit = options.get("limit")

        if window_days < 0:
            self.stdout.write(self.style.ERROR("--window-days cannot be negative."))
            return
        if limit is not None and limit <= 0:
            self.stdout.write(self.style.ERROR("--limit must be a positive integer."))
            return

        lambings_qs = (
            Lambing.objects.filter(is_active=False, actual_lambing_date__isnull=False)
            .select_related("sheep__tag", "ewe__tag")
            .order_by("-actual_lambing_date", "-id")
        )

        lambings = list(lambings_qs)
        if not lambings:
            self.stdout.write(self.style.WARNING("No completed lambings found."))
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
            self.stdout.write(self.style.WARNING("No lambings matched the filters."))
            return

        min_actual_date = min(l.actual_lambing_date for l in lambings)
        max_actual_date = max(l.actual_lambing_date for l in lambings)
        date_from = min_actual_date - timedelta(days=window_days)
        date_to = max_actual_date + timedelta(days=window_days)

        mothers_set = {
            _normalize_tag(lambing.get_mother_tag())
            for lambing in lambings
            if _normalize_tag(lambing.get_mother_tag())
        }

        # Map key: (normalized_mother_tag, birth_date)
        # Value: {"count": int, "female_tags": [str], "male_tags": [str]}
        children_by_key = defaultdict(
            lambda: {
                "count": 0,
                "all_tag_set": set(),
                "female_tags": [],
                "female_tag_set": set(),
                "male_tags": [],
                "male_tag_set": set(),
            }
        )

        def add_child(model_qs, sex):
            for child_id, tag_number, mother_raw, birth_date in model_qs:
                mother_norm = _normalize_tag(mother_raw)
                if not mother_norm or mother_norm not in mothers_set:
                    continue
                key = (mother_norm, birth_date)
                bucket = children_by_key[key]

                child_tag = (tag_number or "").strip()
                child_key = child_tag or f"__no_tag__{child_id}"
                if child_key in bucket["all_tag_set"]:
                    continue

                bucket["all_tag_set"].add(child_key)
                bucket["count"] += 1

                if not child_tag:
                    continue

                if sex == "female":
                    if child_tag not in bucket["female_tag_set"]:
                        bucket["female_tag_set"].add(child_tag)
                        bucket["female_tags"].append(child_tag)
                else:
                    if child_tag not in bucket["male_tag_set"]:
                        bucket["male_tag_set"].add(child_tag)
                        bucket["male_tags"].append(child_tag)

        ewe_children_qs = Ewe.objects.filter(
            birth_date__isnull=False,
            birth_date__gte=date_from,
            birth_date__lte=date_to,
            mother__isnull=False,
        ).values_list("id", "tag__tag_number", "mother", "birth_date")

        sheep_children_qs = Sheep.objects.filter(
            birth_date__isnull=False,
            birth_date__gte=date_from,
            birth_date__lte=date_to,
            mother__isnull=False,
        ).values_list("id", "tag__tag_number", "mother", "birth_date")

        ram_children_qs = Ram.objects.filter(
            birth_date__isnull=False,
            birth_date__gte=date_from,
            birth_date__lte=date_to,
            mother__isnull=False,
        ).values_list("id", "tag__tag_number", "mother", "birth_date")

        add_child(ewe_children_qs, "female")
        add_child(sheep_children_qs, "female")
        add_child(ram_children_qs, "male")

        stats = {
            "processed": 0,
            "no_mother": 0,
            "no_children_in_window": 0,
            "ambiguous_skipped": 0,
            "unchanged": 0,
            "updated": 0,
            "date_changed": 0,
            "live_count_changed": 0,
        }
        changed_rows = []

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

                current_date = lambing.actual_lambing_date

                candidates = []
                for day_delta in range(-window_days, window_days + 1):
                    candidate_date = current_date + timedelta(days=day_delta)
                    key = (mother_norm, candidate_date)
                    child_info = children_by_key.get(key)
                    candidate_count = child_info["count"] if child_info else 0
                    candidates.append((candidate_date, day_delta, candidate_count, child_info))

                max_count = max(c[2] for c in candidates) if candidates else 0
                if max_count <= 0:
                    stats["no_children_in_window"] += 1
                    continue

                best_candidates = [c for c in candidates if c[2] == max_count]

                selected = None
                # Keep current date if it is among best candidates.
                current_best = [c for c in best_candidates if c[1] == 0]
                if current_best:
                    selected = current_best[0]
                elif len(best_candidates) == 1:
                    selected = best_candidates[0]
                else:
                    # If tie remains, try nearest by abs(delta). If still tie, skip.
                    min_abs_delta = min(abs(c[1]) for c in best_candidates)
                    nearest = [c for c in best_candidates if abs(c[1]) == min_abs_delta]
                    if len(nearest) == 1:
                        selected = nearest[0]

                if not selected:
                    stats["ambiguous_skipped"] += 1
                    continue

                selected_date, _, selected_count, selected_info = selected
                new_date = selected_date
                new_live_count = selected_count

                date_changed = lambing.actual_lambing_date != new_date
                live_changed = (lambing.number_of_lambs or 0) != new_live_count

                female_tags = []
                male_tags = []
                if selected_info:
                    female_tags = sorted(selected_info["female_tags"], key=lambda x: x.lower())
                    male_tags = sorted(selected_info["male_tags"], key=lambda x: x.lower())

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
                        merged_tags = female_tags + male_tags
                        optional_updates[field_name] = "; ".join(merged_tags)
                        break

                optional_changed = any(
                    getattr(lambing, field_name) != field_value
                    for field_name, field_value in optional_updates.items()
                )

                if not date_changed and not live_changed and not optional_changed:
                    stats["unchanged"] += 1
                    continue

                old_date = lambing.actual_lambing_date
                old_live = lambing.number_of_lambs or 0

                lambing.actual_lambing_date = new_date
                lambing.number_of_lambs = new_live_count
                for field_name, field_value in optional_updates.items():
                    setattr(lambing, field_name, field_value)

                if date_changed:
                    stats["date_changed"] += 1
                if live_changed:
                    stats["live_count_changed"] += 1

                stats["updated"] += 1
                changed_rows.append(
                    {
                        "id": lambing.id,
                        "mother": lambing.get_mother_tag() or "-",
                        "old_date": old_date,
                        "new_date": new_date,
                        "old_live": old_live,
                        "new_live": new_live_count,
                    }
                )

                if not dry_run:
                    update_fields = ["actual_lambing_date", "number_of_lambs"]
                    update_fields.extend(optional_updates.keys())
                    lambing.save(update_fields=update_fields)

            if dry_run:
                transaction.set_rollback(True)

        mode = "DRY-RUN" if dry_run else "APPLIED"
        self.stdout.write(self.style.SUCCESS(f"[{mode}] Lambing sync finished"))
        self.stdout.write(f"Processed lambings: {stats['processed']}")
        self.stdout.write(f"Updated: {stats['updated']}")
        self.stdout.write(f"  - Date changed: {stats['date_changed']}")
        self.stdout.write(f"  - number_of_lambs changed: {stats['live_count_changed']}")
        self.stdout.write(f"Unchanged: {stats['unchanged']}")
        self.stdout.write(f"Skipped (no mother): {stats['no_mother']}")
        self.stdout.write(f"Skipped (no children in window): {stats['no_children_in_window']}")
        self.stdout.write(f"Skipped (ambiguous tie): {stats['ambiguous_skipped']}")

        if changed_rows:
            self.stdout.write("")
            self.stdout.write("First 20 changes:")
            for row in changed_rows[:20]:
                self.stdout.write(
                    f"  Lambing #{row['id']} | mother {row['mother']} | "
                    f"date {row['old_date']} -> {row['new_date']} | "
                    f"live {row['old_live']} -> {row['new_live']}"
                )

            if len(changed_rows) > 20:
                self.stdout.write(f"  ... and {len(changed_rows) - 20} more changes")
