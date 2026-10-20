from django.db import migrations, models


OLD_STATUS = "Продажа на племя"
TARGET_STATUS = "Реализация в живом весе"


def merge_breeding_sale_status(apps, schema_editor):
    alias = schema_editor.connection.alias
    status = apps.get_model("veterinary", "Status")
    history = apps.get_model("veterinary", "StatusHistory")
    archive_act = apps.get_model("animals", "ArchiveAct")
    animal_case = apps.get_model("inventory", "AnimalCase")
    animal_models = [
        apps.get_model("animals", name) for name in ("Maker", "Ram", "Ewe", "Sheep")
    ]

    old = status.objects.using(alias).select_for_update().filter(status_type=OLD_STATUS).first()
    old_acts = archive_act.objects.using(alias).filter(status_name=OLD_STATUS)
    if old is None and not old_acts.exists():
        return

    affected_tags = set(old_acts.values_list("tag_id", flat=True))
    if old is not None:
        affected_tags.update(
            history.objects.using(alias).filter(
                models.Q(old_status_id=old.pk) | models.Q(new_status_id=old.pk)
            ).values_list("tag_id", flat=True)
        )
        for model in animal_models:
            affected_tags.update(
                model.objects.using(alias).filter(animal_status_id=old.pk)
                .values_list("tag_id", flat=True)
            )

    # Warehouse snapshots are immutable. Do not silently invalidate their source fingerprints.
    case_count = animal_case.objects.using(alias).filter(source_tag_id__in=affected_tags).count()
    if case_count:
        raise RuntimeError(
            f"Объединение статусов остановлено: найдено складских карточек для проверки: {case_count}. "
            "Сначала сверьте их исходные архивные данные; складские снимки не изменены."
        )

    target, _ = status.objects.using(alias).get_or_create(
        status_type=TARGET_STATUS, defaults={"color": "#ff0080"},
    )
    if old is not None:
        # Bulk updates preserve archive flags, timestamps, notes and historical records.
        for model in animal_models:
            model.objects.using(alias).filter(animal_status_id=old.pk).update(animal_status_id=target.pk)
        history.objects.using(alias).filter(old_status_id=old.pk).update(old_status_id=target.pk)
        history.objects.using(alias).filter(new_status_id=old.pk).update(new_status_id=target.pk)

    old_acts.update(status_name=TARGET_STATUS)
    if old is not None:
        status.objects.using(alias).filter(pk=old.pk).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("veterinary", "0020_barn_calculator_profile"),
        ("animals", "0037_rejection_history_manual_dates"),
        ("inventory", "0003_orderline_animal_type"),
    ]

    operations = [
        # The original per-row status cannot be recovered by an automatic reverse migration.
        migrations.RunPython(merge_breeding_sale_status),
        # Flush deferred FK checks before altering the referenced PostgreSQL table.
        migrations.RunSQL("SET CONSTRAINTS ALL IMMEDIATE", reverse_sql=migrations.RunSQL.noop),
        migrations.AddConstraint(
            model_name="status",
            constraint=models.CheckConstraint(
                check=~models.Q(status_type=OLD_STATUS),
                name="status_no_breeding_sale",
            ),
        ),
    ]
