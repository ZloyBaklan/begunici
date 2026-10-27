"""Monthly numbering per act type. Technical record/download IDs stay unchanged."""

from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

from django.db import connection, transaction
from django.utils import timezone


_cache = ContextVar("act_number_cache", default=None)
ORDER = {
    name: index
    for index, name in enumerate(
        (
            "archive",
            "transfer",
            "weight",
            "progeny",
            "rejection",
            "sp55",
            "feed_writeoff",
            "vet_writeoff",
            "sp51",
            "breeding",
        )
    )
}


@dataclass(frozen=True)
class Source:
    kind: str
    key: str
    date: object
    legacy: str = ""

    @property
    def identity(self):
        return self.kind, str(self.key)


class ActNumberingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _cache.set({})
        try:
            return self.get_response(request)
        finally:
            _cache.reset(token)


def group_source(kind, group):
    if kind == "transfer":
        key = f"{group['transfer_date']}:{group.get('old_place_id') or 0}:{group.get('new_place_id') or 0}"
        return Source(kind, key, group["transfer_date"])
    if kind == "weight":
        return Source(
            kind,
            f"{group['weighing_date']}:{group['previous_weight_date']}",
            group["weighing_date"],
        )
    if kind == "progeny":
        return Source(
            kind, f"{group['year']:04d}-{group['month']:02d}", group["act_date"]
        )
    return Source("rejection", str(group["act_date"]), group["act_date"])


def archive_source(act, group_dates=None):
    act_date = act.act_date or act.status_date
    if act.act_group_key:
        if group_dates is None:
            dates = archive_group_dates(act.act_group_key)
            act_date = min(dates) if dates else None
        else:
            act_date = group_dates.get(act.act_group_key)
    return Source(
        "archive",
        f"group:{act.act_group_key}" if act.act_group_key else f"tag:{act.tag_id}",
        act_date,
        act.act_number or "",
    )


def archive_group_dates(group_key):
    from .models import ArchiveAct

    return [
        act_date or status_date
        for act_date, status_date in ArchiveAct.objects.filter(
            act_group_key=group_key
        ).values_list("act_date", "status_date")
        if act_date or status_date
    ]


def inventory_source(document):
    if document.kind == "sp55":
        return Source("sp55", str(document.pk), document.date, document.number or "")
    if document.kind == "sp54":
        from .models import ArchiveAct

        case = document.animals.order_by("pk").first()
        if case:
            frozen = case.snapshot.get("archive_act") or {}
            if frozen.get("act_group_key"):
                key = f"group:{frozen['act_group_key']}"
                current = archive_group_dates(frozen["act_group_key"])
                if current:
                    return Source("archive", key, min(current), document.number or "")
            else:
                act = ArchiveAct.objects.filter(tag_id=case.source_tag_id).first()
                if act:
                    return archive_source(act)
                key = f"tag:{case.source_tag_id}"
            value = frozen.get("act_date") or frozen.get("status_date")
            return Source(
                "archive",
                key,
                date.fromisoformat(value) if value else case.archive_date,
                document.number or "",
            )
        return Source(
            "archive", f"inventory:{document.pk}", document.date, document.number or ""
        )
    return None


def collect_sources():
    from .models import ARCHIVE_STATUS_NAMES, ActNumber, ArchiveAct
    from .transfer_acts import build_transfer_act_groups
    from .weight_acts import build_weight_act_groups
    from .progeny_acts import build_progeny_act_groups
    from .rejection_acts import build_rejection_act_groups
    from begunici.app_types.inventory.models import Document
    from begunici.app_types.feed_inventory.models import FeedDocument
    from begunici.app_types.vet_inventory.models import VetDocument

    sources = {
        (item.source_type, item.source_key): Source(
            item.source_type, item.source_key, item.act_date
        )
        for item in ActNumber.objects.all()
    }
    for kind, builder in (
        ("transfer", build_transfer_act_groups),
        ("weight", build_weight_act_groups),
        ("progeny", build_progeny_act_groups),
        ("rejection", build_rejection_act_groups),
    ):
        for group in builder(numbered=False):
            spec = group_source(kind, group)
            sources[spec.identity] = spec
    archive_keys = set()
    acts = list(
        ArchiveAct.objects.filter(status_name__in=ARCHIVE_STATUS_NAMES).order_by("pk")
    )
    group_dates = {}
    for act in acts:
        value = act.act_date or act.status_date
        if act.act_group_key and value:
            group_dates[act.act_group_key] = min(
                group_dates.get(act.act_group_key, value), value
            )
    for act in acts:
        spec = archive_source(act, group_dates)
        if spec.date:
            previous = sources.get(spec.identity)
            if (
                spec.identity not in archive_keys
                or not previous
                or spec.date < previous.date
            ):
                sources[spec.identity] = spec
            archive_keys.add(spec.identity)
    from .models import Maker, Ram, Ewe, Sheep
    from .archive_acts import normalize_date
    from begunici.app_types.veterinary.vet_models import StatusHistory

    act_tags = ArchiveAct.objects.values_list("tag_id", flat=True)
    fallback_tags = {}
    for model in (Maker, Ram, Ewe, Sheep):
        fallback_tags.update(
            model.objects.filter(
                is_archived=True, animal_status__status_type__in=ARCHIVE_STATUS_NAMES
            )
            .exclude(tag_id__in=act_tags)
            .values_list("tag_id", "animal_status_id")
        )
    found = set()
    for tag_id, status_id, changed_at in (
        StatusHistory.objects.filter(tag_id__in=fallback_tags)
        .order_by("-change_date", "-id")
        .values_list("tag_id", "new_status_id", "change_date")
    ):
        if tag_id not in found and fallback_tags[tag_id] == status_id and changed_at:
            spec = Source("archive", f"tag:{tag_id}", normalize_date(changed_at))
            sources[spec.identity] = spec
            archive_keys.add(spec.identity)
            found.add(tag_id)
    for document in Document.objects.filter(kind__in=["sp54", "sp55"]).prefetch_related(
        "animals"
    ):
        spec = inventory_source(document)
        if spec.date and (document.kind == "sp55" or spec.identity not in archive_keys):
            sources[spec.identity] = spec
    for kind, model in (("feed_writeoff", FeedDocument), ("vet_writeoff", VetDocument)):
        for pk, act_date, legacy in model.objects.filter(kind="writeoff").values_list(
            "pk", "date", "number"
        ):
            spec = Source(kind, str(pk), act_date, legacy or "")
            sources[spec.identity] = spec
    return sources


def ordered_numbers(sources):
    counts, result = {}, {}
    for spec in sorted(
        sources.values(), key=lambda s: (s.date, ORDER.get(s.kind, 99), s.key)
    ):
        bucket = (spec.kind, spec.date.strftime("%Y%m"))
        counts[bucket] = counts.get(bucket, 0) + 1
        result[spec.identity] = (spec, counts[bucket])
    return result


def act_sort_key(number, act_date):
    from .age_utils import as_local_date

    try:
        sequence = int(str(number or "").split("_", 1)[0])
    except ValueError:
        sequence = 0
    return bool(sequence), as_local_date(act_date) or date.min, sequence


@transaction.atomic
def sync_numbers(extra=()):
    from .models import ActNumber

    # Serialize numbering even when the registry is initially empty.
    lock_registry()
    sources = collect_sources()
    for spec in extra:
        if spec.date:
            sources[spec.identity] = spec
    ordered = ordered_numbers(sources)
    existing = {
        (row.source_type, row.source_key): row
        for row in ActNumber.objects.select_for_update()
    }
    previous_numbers = {identity: row.number for identity, row in existing.items()}
    changed = []
    for identity, (spec, sequence) in ordered.items():
        row = existing.get(identity)
        legacy = spec.legacy
        if row and (
            row.act_date != spec.date
            or row.sequence != sequence
            or (legacy and legacy != row.number and legacy not in row.legacy_numbers)
        ):
            changed.append(row)
    # Temporary unique slots permit chronological insertion and movement between months.
    offset = (
        max((row.sequence for row in existing.values()), default=0) + len(ordered) + 1
    )
    for index, row in enumerate(changed, offset):
        row.sequence = index
    if changed:
        ActNumber.objects.bulk_update(changed, ["sequence"])
    new_rows = []
    for identity, (spec, sequence) in ordered.items():
        row = existing.get(identity)
        if row is None:
            row = ActNumber(
                source_type=spec.kind,
                source_key=spec.key,
                act_date=spec.date,
                period=spec.date.strftime("%Y%m"),
                sequence=offset + len(changed) + len(new_rows),
            )
            new_rows.append(row)
            existing[identity] = row
    if new_rows:
        ActNumber.objects.bulk_create(new_rows)
    updates = []
    changed_ids = {(row.source_type, row.source_key) for row in changed + new_rows}
    for identity, (spec, sequence) in ordered.items():
        row = existing[identity]
        new_number = f"{sequence}_{spec.date:%m%y}"
        added_legacy = False
        for legacy in (previous_numbers.get(identity), spec.legacy):
            if legacy and legacy != new_number and legacy not in row.legacy_numbers:
                row.legacy_numbers = [*row.legacy_numbers, legacy]
                added_legacy = True
        if (
            row.act_date != spec.date
            or row.sequence != sequence
            or identity in changed_ids
            or added_legacy
        ):
            row.act_date, row.period, row.sequence = (
                spec.date,
                spec.date.strftime("%Y%m"),
                sequence,
            )
            updates.append(row)
    if updates:
        ActNumber.objects.bulk_update(
            updates, ["act_date", "period", "sequence", "legacy_numbers"]
        )
    return existing


def lock_registry(*, wait=True):
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            function = "pg_advisory_xact_lock" if wait else "pg_try_advisory_xact_lock"
            cursor.execute(f"SELECT {function}(%s)", [5500391026])
            if not wait and not cursor.fetchone()[0]:
                raise ValueError(
                    "Нумерация занята другим пользователем. Повторите команду после завершения операции"
                )


def numbers_for(sources):
    sources = list(sources)
    cache = _cache.get()
    mapping = cache.get("mapping") if cache is not None else None
    if mapping is None or any(
        s.identity not in mapping or mapping[s.identity].act_date != s.date
        for s in sources
        if s.date
    ):
        mapping = sync_numbers(sources)
        if cache is not None:
            cache["mapping"] = mapping
    return {
        spec.identity: mapping[spec.identity].number
        if spec.date and spec.identity in mapping
        else ""
        for spec in sources
    }


def number_for(spec):
    return numbers_for([spec])[spec.identity] if spec.date else ""


def number_groups(kind, groups):
    specs = [group_source(kind, group) for group in groups]
    mapping = numbers_for(specs) if specs else {}
    for group, spec in zip(groups, specs):
        group["display_number"] = mapping[spec.identity]
    return groups


def archive_number(act, animal=None):
    if act:
        return number_for(archive_source(act))
    if animal:
        from .archive_acts import get_archive_status_date

        return number_for(
            Source("archive", f"tag:{animal.tag_id}", get_archive_status_date(animal))
        )
    return ""


def inventory_number(document):
    spec = inventory_source(document)
    return number_for(spec) if spec else document.number or str(document.pk)


def writeoff_number(document, kind):
    return number_for(
        Source(kind, str(document.pk), document.date, document.number or "")
    )


def report_number(kind, key, act_date=None):
    from .models import ActNumber

    existing = ActNumber.objects.filter(source_type=kind, source_key=str(key)).first()
    return number_for(
        Source(
            kind,
            str(key),
            act_date or (existing.act_date if existing else timezone.localdate()),
        )
    )


@contextmanager
def numbering_context(mapping):
    token = _cache.set({"mapping": mapping})
    try:
        yield
    finally:
        _cache.reset(token)


def numbered_excel(content, number, kind):
    """Only change a recognized number cell, never reconstruct accounting data."""
    from io import BytesIO
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(BytesIO(content))
    except Exception:
        return None
    sheet = workbook.worksheets[0]
    if kind == "sp55":
        if not str(sheet["K3"].value or "").startswith("УЧЕТНЫЙ ЛИСТ №"):
            return None
        target, value = "K3", f"УЧЕТНЫЙ ЛИСТ № {number}"
    elif kind == "archive":
        if str(sheet["G1"].value or "").startswith("АКТ"):
            target, value = "G1", f"АКТ  № {number}"
        elif "СП-54" in str(sheet["AI1"].value or "") and "А К Т" in str(
            sheet["X4"].value or ""
        ):
            target, value = "AA4", number
        elif sheet.title == "Данные СП-54":
            footer = next(
                (
                    cell
                    for cell in sheet["A"]
                    if "Приложите исправленный СП-54" in str(cell.value or "")
                ),
                None,
            )
            if footer is None:
                return None
            target, value = (
                footer.coordinate,
                f"СП-54 № {number}. Приложите исправленный СП-54 для утверждения этих данных.",
            )
        else:
            return None
    else:
        return None
    if sheet[target].value == value:
        return content
    sheet[target] = value
    sheet[target].data_type = "s"
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def is_generated_version(version, generated_hashes=None):
    if version.origin == "generated":
        return True
    if generated_hashes is None:
        from begunici.app_types.inventory.models import DocumentVersion

        generated_hashes = DocumentVersion.objects.filter(
            document_id=version.document_id, origin="generated"
        ).values_list("sha256", flat=True)
    return version.sha256 in generated_hashes
