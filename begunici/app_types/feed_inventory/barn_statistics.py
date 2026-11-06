"""Read-only weekly head counts, with location at the event date."""
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone
from begunici.app_types.animals import feed_plan as animals
from begunici.app_types.animals.models import ArchiveAct
from begunici.app_types.veterinary.vet_models import PlaceMovement, StatusHistory


def weekly_movements(barn, today=None):
    from .barns import place_barn
    today = today or timezone.localdate()
    start = today - timedelta(days=6)
    midnight = lambda day: timezone.make_aware(datetime.combine(day, time.min))
    lower, upper = midnight(start), midnight(today + timedelta(days=1))
    locations, birthdays = {}, {}
    for model in (animals.Maker, animals.Sheep, animals.Ewe, animals.Ram):
        for tag, place, birth in model.objects.values_list("tag_id", "place__sheepfold", "birth_date"):
            locations[tag] = place_barn(place)
            if birth and start <= birth <= today:
                birthdays[tag] = birth
    movements = list(PlaceMovement.objects.filter(created_at__gte=lower)
        .select_related("old_place", "new_place").order_by("created_at", "pk"))
    by_tag = defaultdict(list)
    arrived, transferred, departed = set(), set(), set()
    for event in movements:
        by_tag[event.tag_id].append(event)
        if event.created_at >= upper:
            continue
        old, new = place_barn(event.old_place), place_barn(event.new_place)
        if old != new:
            if new == barn:
                arrived.add(event.tag_id)
            if old == barn and new is not None:
                transferred.add(event.tag_id)

    def location_at(tag, instant):
        # First later movement records the location before it happened. This
        # also works when the animal was moved after the displayed seven days.
        later = next((event for event in by_tag[tag] if event.created_at >= instant), None)
        return place_barn(later.old_place) if later else locations.get(tag)

    for tag, birth in birthdays.items():
        if location_at(tag, midnight(birth)) == barn:
            arrived.add(tag)
    # Archive business dates take precedence over the time an operator entered
    # the status. Status history remains the fallback for entries without acts.
    acts = {}
    histories = list(StatusHistory.objects.filter(change_date__gte=lower, change_date__lt=upper,
        new_status__status_type__in=animals.ARCHIVE_STATUS_NAMES).select_related("new_status").order_by("change_date", "pk"))
    for act in ArchiveAct.objects.filter(status_name__in=animals.ARCHIVE_STATUS_NAMES, status_date__isnull=False).order_by("updated_at", "pk"):
        acts[(act.tag_id, act.status_name)] = act
    for act in acts.values():
        matching = [event for event in histories if event.tag_id == act.tag_id and event.new_status.status_type == act.status_name
                    and timezone.localdate(event.change_date) == act.status_date]
        instant = matching[-1].change_date if matching else midnight(act.status_date)
        if start <= act.status_date <= today and location_at(act.tag_id, instant) == barn:
            departed.add(act.tag_id)
    for event in histories:
        if (event.tag_id, event.new_status.status_type) not in acts and location_at(event.tag_id, event.change_date) == barn:
            departed.add(event.tag_id)
    return {"arrived": len(arrived), "transferred": len(transferred), "left": len(departed),
            "from": start.strftime("%d.%m"), "to": today.strftime("%d.%m")}
