from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0030_alter_archiveact_fatness"),
    ]

    operations = [
        migrations.CreateModel(
            name="DashboardPlanParameter",
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
                    "key",
                    models.CharField(
                        db_index=True,
                        max_length=100,
                        unique=True,
                        verbose_name="Ключ",
                    ),
                ),
                (
                    "label",
                    models.CharField(max_length=255, verbose_name="Параметр"),
                ),
                (
                    "plan_value",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        verbose_name="План",
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveIntegerField(default=0, verbose_name="Порядок"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Дата обновления"),
                ),
            ],
            options={
                "verbose_name": "Плановый параметр",
                "verbose_name_plural": "Плановые параметры",
                "ordering": ["sort_order", "id"],
            },
        ),
    ]
