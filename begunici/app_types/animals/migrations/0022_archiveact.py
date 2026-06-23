from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("veterinary", "0018_veterinarycare_other_class_custom_type"),
        ("animals", "0021_lambinggroup_lambing_completion_type_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArchiveAct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("animal_type", models.CharField(max_length=30, verbose_name="Тип животного")),
                ("status_name", models.CharField(db_index=True, max_length=100, verbose_name="Архивный статус")),
                ("status_date", models.DateField(blank=True, null=True, verbose_name="Дата присвоения статуса")),
                ("act_number", models.CharField(blank=True, default="", max_length=255, verbose_name="Номер акта")),
                ("act_date", models.DateField(blank=True, null=True, verbose_name="Дата акта")),
                (
                    "live_weight",
                    models.DecimalField(
                        blank=True,
                        decimal_places=1,
                        max_digits=7,
                        null=True,
                        verbose_name="Живая масса (кг)",
                    ),
                ),
                (
                    "fatness",
                    models.CharField(
                        blank=True,
                        choices=[("ср", "ср"), ("н/ср", "н/ср"), ("выс", "выс")],
                        default="",
                        max_length=20,
                        verbose_name="Упитанность",
                    ),
                ),
                ("diagnosis", models.TextField(blank=True, default="", verbose_name="Диагноз / основание")),
                (
                    "worker_name",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="ФИО закрепленного работника",
                    ),
                ),
                ("download_on_archive", models.BooleanField(default=False, verbose_name="Скачивать при архивировании")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                (
                    "tag",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="archive_acts",
                        to="veterinary.tag",
                        verbose_name="Бирка",
                    ),
                ),
            ],
            options={
                "verbose_name": "Акт архивирования",
                "verbose_name_plural": "Акты архивирования",
                "ordering": ["-updated_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="archiveact",
            index=models.Index(fields=["tag", "status_name"], name="archive_act_tag_status_idx"),
        ),
    ]
