from django.db import migrations, models
from django.db.models import F, OuterRef, Subquery
from django.db.models.functions import Coalesce
import django.db.models.deletion


def set_active_tracking(apps, schema_editor):
    alias = schema_editor.connection.alias
    Care = apps.get_model("veterinary", "VeterinaryCare")
    Group = apps.get_model("animals", "LambingGroup")
    Lambing = apps.get_model("animals", "Lambing")
    default_id = None
    for care in Care.objects.using(alias).order_by("pk"):
        medication = (care.medication or "").casefold()
        if "пастанарм" in medication and "перв" in medication:
            default_id = care.pk
            break
    if default_id is None:
        return
    Group.objects.using(alias).filter(is_active=True).update(tracked_veterinary_care_id=default_id)
    placement_date = Group.objects.using(alias).filter(pk=OuterRef("source_group_id")).values("placement_date")[:1]
    Lambing.objects.using(alias).filter(is_active=True).update(
        tracked_veterinary_care_id=default_id,
        tracked_veterinary_from_date=Coalesce(Subquery(placement_date), F("start_date")),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("animals", "0040_actnumber_per_type"),
        ("veterinary", "0021_merge_breeding_sale_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="lambinggroup", name="tracked_veterinary_care",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="tracked_lambing_groups", to="veterinary.veterinarycare",
                                    verbose_name="Отслеживаемая ветобработка"),
        ),
        migrations.AddField(
            model_name="lambing", name="tracked_veterinary_care",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="tracked_lambings", to="veterinary.veterinarycare",
                                    verbose_name="Отслеживаемая ветобработка"),
        ),
        migrations.AddField(
            model_name="lambing", name="tracked_veterinary_from_date",
            field=models.DateField(blank=True, null=True, verbose_name="Дата начала отслеживания ветобработки"),
        ),
        migrations.RunPython(set_active_tracking, migrations.RunPython.noop),
    ]
