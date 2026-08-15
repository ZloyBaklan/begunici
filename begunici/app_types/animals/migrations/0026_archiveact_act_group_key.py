from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0025_animal_is_reject"),
    ]

    operations = [
        migrations.AddField(
            model_name="archiveact",
            name="act_group_key",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="Ключ общего акта",
            ),
        ),
    ]
