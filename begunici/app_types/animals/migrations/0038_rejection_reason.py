from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("animals", "0037_rejection_history_manual_dates"),
        ("veterinary", "0021_merge_breeding_sale_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="animalrejectionhistory",
            name="reason",
            field=models.TextField(blank=True, default="", verbose_name="Причина выбраковки"),
        ),
        # Existing database triggers and direct SQL assignments omit this column.
        migrations.RunSQL(
            "ALTER TABLE animals_animalrejectionhistory ALTER COLUMN reason SET DEFAULT ''",
            reverse_sql="ALTER TABLE animals_animalrejectionhistory ALTER COLUMN reason DROP DEFAULT",
        ),
    ]
