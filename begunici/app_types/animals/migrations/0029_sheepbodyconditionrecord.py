from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0028_animalnotehistory"),
        ("veterinary", "0019_remove_place_date_of_transfer"),
    ]

    operations = [
        migrations.CreateModel(
            name="SheepBodyConditionRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "condition_index",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "кахексия (истощение)"),
                            (2, "ниже средней"),
                            (3, "средняя"),
                            (4, "выше средней"),
                            (5, "высшая (ожирение)"),
                        ],
                        db_index=True,
                        verbose_name="Индекс упитанности",
                    ),
                ),
                (
                    "measurement_date",
                    models.DateField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        verbose_name="Дата измерения",
                    ),
                ),
                ("note", models.TextField(blank=True, default="", verbose_name="Примечание")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                (
                    "tag",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sheep_body_condition_records",
                        to="veterinary.tag",
                        verbose_name="Бирка",
                    ),
                ),
            ],
            options={
                "verbose_name": "Запись упитанности овцематки",
                "verbose_name_plural": "История упитанности овцематок",
                "ordering": ["-measurement_date", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="sheepbodyconditionrecord",
            index=models.Index(fields=["tag", "-measurement_date"], name="sheep_bcs_tag_date_idx"),
        ),
    ]
