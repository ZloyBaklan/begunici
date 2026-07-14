from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0023_repair_lambing_group_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="lambing",
            name="mother_category_at_start",
            field=models.CharField(
                blank=True,
                choices=[
                    ("sheep", "Овцематка"),
                    ("ewe", "Ярка"),
                ],
                db_index=True,
                help_text=(
                    "Фиксируется для новых окотов. Старые пустые записи "
                    "считаются по старой логике."
                ),
                max_length=10,
                null=True,
                verbose_name="Категория матери на начало случки",
            ),
        ),
    ]
