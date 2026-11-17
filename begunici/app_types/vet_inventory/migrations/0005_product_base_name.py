from django.db import migrations, models


def set_sql_default(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("ALTER TABLE vet_inventory_vetproduct ALTER COLUMN base_name SET DEFAULT ''")


def drop_sql_default(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("ALTER TABLE vet_inventory_vetproduct ALTER COLUMN base_name DROP DEFAULT")


class Migration(migrations.Migration):
    dependencies = [("vet_inventory", "0004_packaging_and_dosage")]

    operations = [
        migrations.AddField(
            model_name="vetproduct", name="base_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.RunPython(set_sql_default, drop_sql_default),
    ]
