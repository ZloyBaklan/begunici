from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0024_lambing_mother_category_at_start"),
    ]

    operations = [
        migrations.AddField(
            model_name="maker",
            name="is_reject",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Отдельная отметка назначения животного, не статус.",
                verbose_name="Брак",
            ),
        ),
        migrations.AddField(
            model_name="ram",
            name="is_reject",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Отдельная отметка назначения животного, не статус.",
                verbose_name="Брак",
            ),
        ),
        migrations.AddField(
            model_name="ewe",
            name="is_reject",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Отдельная отметка назначения животного, не статус.",
                verbose_name="Брак",
            ),
        ),
        migrations.AddField(
            model_name="sheep",
            name="is_reject",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Отдельная отметка назначения животного, не статус.",
                verbose_name="Брак",
            ),
        ),
    ]
