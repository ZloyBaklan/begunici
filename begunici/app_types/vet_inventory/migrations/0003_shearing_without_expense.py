from django.db import migrations
from django.db.models import F


def exclude_pending_shearing(apps, schema_editor):
    alias = schema_editor.connection.alias
    Care = apps.get_model("veterinary", "VeterinaryCare")
    Veterinary = apps.get_model("veterinary", "Veterinary")
    Treatment = apps.get_model("vet_inventory", "VetTreatment")
    care_ids = {
        pk
        for pk, care_type, care_name in Care.objects.using(alias).values_list(
            "pk", "care_type", "care_name"
        )
        if any(
            str(value or "").strip().casefold() == "стрижка"
            for value in (care_type, care_name)
        )
    }
    pending = list(
        Treatment.objects.using(alias).filter(state="pending", document_id__isnull=True)
    )
    sources = dict(
        Veterinary.objects.using(alias)
        .filter(pk__in=[entry.source_id for entry in pending])
        .values_list("pk", "veterinary_care_id")
    )
    ids = []
    for entry in pending:
        current_care = sources.get(entry.source_id)
        if current_care is not None:
            shearing = current_care in care_ids
        else:
            shearing = (
                str(entry.snapshot.get("care") or "")
                .rsplit(":", 1)[-1]
                .strip()
                .casefold()
                == "стрижка"
            )
        if shearing:
            ids.append(entry.pk)
    Treatment.objects.using(alias).filter(
        pk__in=ids, state="pending", document_id__isnull=True
    ).update(
        state="excluded",
        issue="Стрижка не требует расхода ветпрепаратов",
        manual=False,
        product_id=None,
        quantity=0,
        calculation={"mode_label": "Без расхода", "quantity": "0"},
        revision=F("revision") + 1,
    )


class Migration(migrations.Migration):
    dependencies = [("vet_inventory", "0002_accounting_start")]

    operations = [
        migrations.RunPython(exclude_pending_shearing, migrations.RunPython.noop)
    ]
