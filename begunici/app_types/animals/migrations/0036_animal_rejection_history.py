import re
from collections import defaultdict
from zoneinfo import ZoneInfo

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


ANIMAL_TYPES = {
    "Овцематка": "Sheep", "Овца": "Sheep", "Sheep": "Sheep",
    "Ярка": "Ewe", "Ewe": "Ewe", "Баранчик": "Ram", "Ram": "Ram",
    "Баран-Производитель": "Maker", "Баран-производитель": "Maker", "Maker": "Maker",
}
FLAG_CHANGE = re.compile(
    r"(?:^Изменения:\s*|;\s*)Назначение:(?:\s*Брак:)?\s*"
    r"(Не указано|True|False|Да|Нет)\s*(?:→|->)\s*"
    r"(Не указано|True|False|Да|Нет)(?=;|$)", re.IGNORECASE,
)
TAG_CHANGE = re.compile(
    r"(?:^Изменения:\s*|;\s*)Бирка:\s*(\S+)\s*(?:→|->)\s*([^;\s]+)"
)
RETAG_CHANGE = re.compile(
    r"^Перебирковано животное: .+?\s+(\S+)\s*(?:→|->)\s*([^;\s]+)"
)
EDIT_ACTIONS = {"Редактирование животного", "Архивирование животного", "Восстановление из архива"}


def backfill_rejection_history(apps, schema_editor):
    alias = schema_editor.connection.alias
    history = apps.get_model("animals", "AnimalRejectionHistory")
    if history.objects.using(alias).exists():
        return
    tags = apps.get_model("veterinary", "Tag")
    logs = apps.get_model("animals", "UserActionLog")
    identities = defaultdict(set)
    issued = {}
    for tag_id, number, issue_date in tags.objects.using(alias).values_list("id", "tag_number", "issue_date"):
        identities[number.casefold()].add(tag_id)
        issued[tag_id] = issue_date

    current_states = {}
    for animal_type in ("Sheep", "Ewe", "Ram", "Maker"):
        animal_model = apps.get_model("animals", animal_type)
        for tag_id, rejected in animal_model.objects.using(alias).values_list("tag_id", "is_reject"):
            current_states[tag_id] = (animal_type, rejected)

    events = defaultdict(list)
    candidates = logs.objects.using(alias).filter(object_type__in=ANIMAL_TYPES).filter(
        models.Q(description__icontains="Назначение:")
        | models.Q(description__contains="Бирка:")
        | models.Q(action_type="Перебиркование животного")
    ).order_by("-timestamp", "-id")
    for log in candidates.iterator():
        renamed = TAG_CHANGE.search(log.description) if log.action_type in EDIT_ACTIONS else None
        if log.action_type == "Перебиркование животного":
            renamed = RETAG_CHANGE.search(log.description)
        changed = FLAG_CHANGE.search(log.description) if log.action_type in EDIT_ACTIONS else None
        local_date = log.timestamp.astimezone(ZoneInfo("Europe/Moscow")).date()
        matched_ids = {
            tag_id for tag_id in identities.get((log.object_id or "").strip().casefold(), set())
            if not issued[tag_id] or issued[tag_id] <= local_date
        }
        if changed and len(matched_ids) == 1:
            tag_id = next(iter(matched_ids))
            old_value, new_value = [value.casefold() in {"true", "да"} for value in changed.groups()]
            if tag_id in current_states and old_value != new_value:
                events[tag_id].append((log, old_value, new_value))
        # Reverse renames chronologically so a reused tag cannot steal another animal's log.
        if renamed:
            old_number, new_number = [number.casefold() for number in renamed.groups()]
            if old_number != new_number:
                renamed_ids = identities.pop(new_number, set())
                identities[old_number].update(renamed_ids)

    recorded_at = timezone.now()
    entries = []
    for tag_id, (animal_type, rejected) in current_states.items():
        state = False
        for log, old_value, new_value in reversed(events[tag_id]):
            if state != old_value:
                entries.append(history(
                    tag_id=tag_id, animal_type=ANIMAL_TYPES[log.object_type],
                    old_is_reject=None, new_is_reject=old_value,
                    change_date=None, recorded_at=recorded_at, source="legacy",
                ))
            entries.append(history(
                tag_id=tag_id, animal_type=ANIMAL_TYPES[log.object_type],
                old_is_reject=old_value, new_is_reject=new_value,
                change_date=log.timestamp, recorded_at=recorded_at,
                source="log", source_log_id=log.id,
            ))
            state = new_value
        if state != rejected:
            entries.append(history(
                tag_id=tag_id, animal_type=animal_type, old_is_reject=None,
                new_is_reject=rejected, change_date=None,
                recorded_at=recorded_at, source="legacy",
            ))
    history.objects.using(alias).bulk_create(entries)


TRIGGER_FUNCTION = """
CREATE FUNCTION animals_capture_rejection_change() RETURNS trigger AS $$
DECLARE
    previous_flag boolean;
    previous_exists boolean;
    changed_at timestamptz := statement_timestamp();
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.is_reject IS NOT DISTINCT FROM OLD.is_reject THEN
        RETURN NEW;
    END IF;
    PERFORM id FROM veterinary_tag WHERE id = NEW.tag_id FOR UPDATE;
    IF TG_OP = 'UPDATE' THEN
        previous_flag := OLD.is_reject;
    ELSE
        -- A type conversion inserts a new model row with the same permanent Tag.
        SELECT a.is_reject INTO previous_flag FROM (
            SELECT 'animals_sheep' AS animal_table, id, tag_id, is_reject FROM animals_sheep
            UNION ALL SELECT 'animals_ewe', id, tag_id, is_reject FROM animals_ewe
            UNION ALL SELECT 'animals_ram', id, tag_id, is_reject FROM animals_ram
            UNION ALL SELECT 'animals_maker', id, tag_id, is_reject FROM animals_maker
        ) a WHERE a.tag_id = NEW.tag_id AND NOT (a.animal_table = TG_TABLE_NAME AND a.id = NEW.id)
        LIMIT 1;
        previous_exists := FOUND;
        IF NOT previous_exists THEN
            SELECT new_is_reject INTO previous_flag FROM animals_animalrejectionhistory
            WHERE tag_id = NEW.tag_id ORDER BY id DESC LIMIT 1;
            previous_exists := FOUND;
        END IF;
        IF NOT previous_exists THEN
            previous_flag := false;
        END IF;
        IF previous_flag = NEW.is_reject THEN
            RETURN NEW;
        END IF;
    END IF;
    INSERT INTO animals_animalrejectionhistory (
        tag_id, animal_type, old_is_reject, new_is_reject,
        change_date, recorded_at, source, source_log_id
    ) VALUES (
        NEW.tag_id, TG_ARGV[0], previous_flag, NEW.is_reject,
        changed_at, changed_at, 'change', NULL
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def install_rejection_triggers(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        raise RuntimeError("Animal rejection history requires PostgreSQL")
    schema_editor.execute(TRIGGER_FUNCTION)
    for animal_type in ("Sheep", "Ewe", "Ram", "Maker"):
        table = apps.get_model("animals", animal_type)._meta.db_table
        schema_editor.execute(
            f'CREATE TRIGGER capture_rejection_change AFTER INSERT OR UPDATE OF is_reject ON "{table}" '
            f"FOR EACH ROW EXECUTE FUNCTION animals_capture_rejection_change('{animal_type}')"
        )


def uninstall_rejection_triggers(apps, schema_editor):
    for animal_type in ("Sheep", "Ewe", "Ram", "Maker"):
        table = apps.get_model("animals", animal_type)._meta.db_table
        schema_editor.execute(f'DROP TRIGGER IF EXISTS capture_rejection_change ON "{table}"')
    schema_editor.execute("DROP FUNCTION IF EXISTS animals_capture_rejection_change()")


class Migration(migrations.Migration):
    dependencies = [("animals", "0035_dashboard_culling_snapshot")]

    operations = [
        migrations.CreateModel(
            name="AnimalRejectionHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("animal_type", models.CharField(max_length=10, verbose_name="Тип животного на момент записи")),
                ("old_is_reject", models.BooleanField(blank=True, null=True, verbose_name="Брак: было")),
                ("new_is_reject", models.BooleanField(verbose_name="Брак: стало")),
                ("change_date", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="Дата изменения")),
                ("recorded_at", models.DateTimeField(default=timezone.now, verbose_name="Дата записи истории")),
                ("source", models.CharField(choices=[("change", "Изменение отметки"), ("log", "Восстановлено из лога"), ("legacy", "Дата изменения неизвестна")], default="change", max_length=10)),
                ("source_log", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rejection_history_entry", to="animals.useractionlog", verbose_name="Исходный лог")),
                ("tag", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rejection_history", to="veterinary.tag", verbose_name="Бирка")),
            ],
            options={
                "ordering": ["-id"],
                "verbose_name": "История назначения брака",
                "verbose_name_plural": "История назначения брака",
                "indexes": [models.Index(fields=["tag", "-id"], name="reject_history_tag_id_idx")],
                "constraints": [models.CheckConstraint(
                    check=(models.Q(source="legacy", change_date__isnull=True)
                           | (models.Q(source__in=["change", "log"]) & models.Q(change_date__isnull=False))),
                    name="reject_history_known_date",
                )],
            },
        ),
        migrations.RunPython(backfill_rejection_history, migrations.RunPython.noop),
        migrations.RunPython(install_rejection_triggers, uninstall_rejection_triggers),
    ]
