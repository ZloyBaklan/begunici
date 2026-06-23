import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0020_shifttransfernote"),
    ]

    operations = [
        migrations.CreateModel(
            name="LambingGroup",
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
                (
                    "placement_date",
                    models.DateField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        verbose_name="Дата постановки в группу",
                    ),
                ),
                (
                    "removal_date",
                    models.DateField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="Дата снятия барана",
                    ),
                ),
                (
                    "note",
                    models.TextField(
                        blank=True,
                        null=True,
                        verbose_name="Примечание",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        verbose_name="Активная группа",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        verbose_name="Дата создания",
                    ),
                ),
                (
                    "ewes",
                    models.ManyToManyField(
                        blank=True,
                        related_name="lambing_groups",
                        to="animals.ewe",
                        verbose_name="Ярки",
                    ),
                ),
                (
                    "maker",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lambing_groups_as_father",
                        to="animals.maker",
                        verbose_name="Баран-Производитель",
                    ),
                ),
                (
                    "ram",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lambing_groups_as_father",
                        to="animals.ram",
                        verbose_name="Баранчик",
                    ),
                ),
                (
                    "sheep",
                    models.ManyToManyField(
                        blank=True,
                        related_name="lambing_groups",
                        to="animals.sheep",
                        verbose_name="Овцематки",
                    ),
                ),
            ],
            options={
                "verbose_name": "Группа случки",
                "verbose_name_plural": "Группы случек",
                "ordering": ["-is_active", "-placement_date", "-id"],
            },
        ),
        migrations.AddField(
            model_name="lambing",
            name="completion_type",
            field=models.CharField(
                choices=[
                    ("normal", "Обычное завершение"),
                    ("early_failure", "Досрочно завершен"),
                ],
                db_index=True,
                default="normal",
                max_length=30,
                verbose_name="Тип завершения",
            ),
        ),
        migrations.AddField(
            model_name="lambing",
            name="source_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lambings",
                to="animals.lambinggroup",
                verbose_name="Группа случки",
            ),
        ),
    ]
