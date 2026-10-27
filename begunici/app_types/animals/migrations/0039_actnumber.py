from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("animals", "0038_rejection_reason")]

    operations = [
        migrations.CreateModel(
            name="ActNumber",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_type", models.CharField(max_length=30)),
                ("source_key", models.CharField(max_length=200)),
                ("act_date", models.DateField()),
                ("period", models.CharField(max_length=6)),
                ("sequence", models.PositiveIntegerField()),
                ("legacy_numbers", models.JSONField(blank=True, default=list)),
            ],
            options={"ordering": ["act_date", "sequence"]},
        ),
        migrations.AddConstraint(
            model_name="actnumber",
            constraint=models.UniqueConstraint(
                fields=("source_type", "source_key"), name="act_number_source_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="actnumber",
            constraint=models.UniqueConstraint(
                fields=("period", "sequence"), name="act_number_month_sequence_unique"
            ),
        ),
    ]
