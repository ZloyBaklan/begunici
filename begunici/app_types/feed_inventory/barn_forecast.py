"""Estimate consumption from dated animal and feed movements."""
from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from begunici.app_types.animals import feed_plan, livestock_movement_acts as herd
from begunici.app_types.veterinary.vet_models import PlaceMovement
from . import barns
from .models import BarnFeedMovement, FeedNorm
from .packaging import group_map


def dates(start, end):
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def daily_headcounts(barn, start, end):
    """Use the end-of-day barn and feeding group of each animal."""
    places = set(barns.places_by_barn()[barn])
    days = dates(start, end)
    counts = {day: dict.fromkeys(feed_plan.FEED_GROUP_LABELS, 0) for day in days}
    unclassified = dict.fromkeys(days, 0)
    if not places:
        return {day: (counts[day], 0) for day in days}

    animals = [animal for _, animal in herd.get_all_animals() if not animal.birth_date or animal.birth_date <= end]
    movements = defaultdict(list)
    for event in PlaceMovement.objects.filter(created_at__date__gt=start).order_by("created_at", "pk"):
        movements[event.tag_id].append(event)
    animals = [animal for animal in animals if animal.place_id in places or any(
        event.old_place_id in places for event in movements[animal.tag_id])]
    tag_ids = {animal.tag_id for animal in animals}
    histories = herd.build_status_history_map(tag_ids)
    archive_dates = herd.build_archive_dates_map(tag_ids, histories)

    for animal in animals:
        transfers = movements[animal.tag_id]
        transfer_dates = [herd.normalize_date(event.created_at) for event in transfers]
        statuses = histories[animal.tag_id]
        status_dates = [herd.normalize_date(event.change_date) for event in statuses]
        for day in days:
            next_transfer = bisect_right(transfer_dates, day)
            place = transfers[next_transfer].old_place_id if next_transfer < len(transfers) else animal.place_id
            if place not in places or not herd.is_active_on_date(animal, histories, archive_dates, day):
                continue
            status_index = bisect_right(status_dates, day)
            if status_index:
                status = statuses[status_index - 1].new_status
            else:
                status = statuses[0].old_status if statuses else animal.animal_status
            group = feed_plan.classify_feed_plan_animal(animal, day, status_name=status.status_type if status else None)
            if group:
                counts[day][group] += 1
            else:
                unclassified[day] += 1
    return {day: (counts[day], unclassified[day]) for day in days}


def consumption_estimate(barn, start, end, rows, plan=None):
    headcounts = daily_headcounts(barn, start, end)
    if plan and plan.get("rows"):
        norms = {(cell["product_id"], row["group"]): Decimal(cell["norm"]) if cell["norm"] != "" else None
                 for row in plan["rows"] for cell in row["cells"]}
    else:
        norms = {(norm.product_id, norm.group): norm.per_head for norm in FeedNorm.objects.filter(product__plan_product__isnull=True)}

    # Keep stock in separate catalogue items. Variants share their feed type's ration.
    groups = defaultdict(list)
    product_groups = group_map()
    for row in rows:
        pk = row["product"].pk
        groups[product_groups[pk]].append(pk)
    balances = {pk: quantity for pk, (quantity, _) in barns.barn_balances(barn, before=start).items()}
    movements = defaultdict(list)
    for movement in BarnFeedMovement.objects.filter(document__barn=barn, document__date__range=(start, end)).values(
            "document__date", "product_id").annotate(quantity=Sum("amount")):
        movements[movement["document__date"]].append((movement["product_id"], movement["quantity"]))
    confirmed_days = set()
    for week in barns.active_weeks(barn).filter(date__range=(start, end)):
        confirmed_days.update(dates(date.fromisoformat(week.payload["start"]), week.date))

    missing_norms = False
    for day, (counts, _) in headcounts.items():
        for pk, quantity in movements[day]:
            balances[pk] = balances.get(pk, barns.ZERO) + quantity
        if day in confirmed_days:
            continue
        for root, variants in groups.items():
            per_group = [(headcount, norms.get((root, group))) for group, headcount in counts.items() if headcount]
            missing_norms |= any(norm is None for _, norm in per_group)
            demand = sum((headcount * (norm or barns.ZERO) for headcount, norm in per_group), barns.ZERO)
            available = {pk: max(barns.ZERO, balances.get(pk, barns.ZERO)) for pk in variants}
            total = sum(available.values(), barns.ZERO)
            if total and demand:
                fraction = min(total, demand) / total
                for pk, quantity in available.items():
                    if quantity:
                        balances[pk] -= quantity * fraction

    for row in rows:
        remaining = max(barns.ZERO, balances.get(row["product"].pk, barns.ZERO)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        row["estimated_remaining"] = min(remaining, row["available"])
        row["estimated_use"] = row["available"] - row["estimated_remaining"]
    end_counts, end_unclassified = headcounts[end]
    return {"heads": sum(end_counts.values()) + end_unclassified,
            "animal_days": sum(sum(counts.values()) + unknown for counts, unknown in headcounts.values()),
            "unclassified_days": sum(unknown for _, unknown in headcounts.values()),
            "missing_norms": missing_norms}
