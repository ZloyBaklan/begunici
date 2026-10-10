from django.db import migrations
from django.db.models import Max


def start_accounting(apps, schema_editor):
    alias = schema_editor.connection.alias
    last = apps.get_model("veterinary", "Veterinary").objects.using(alias).aggregate(last=Max("pk"))["last"] or 0
    apps.get_model("vet_inventory", "VetSettings").objects.using(alias).get_or_create(
        pk=1, defaults={"legacy_treatment_id": last})


class Migration(migrations.Migration):
    dependencies = [("vet_inventory", "0001_initial")]
    operations = [migrations.RunPython(start_accounting, migrations.RunPython.noop)]
