from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0026_archiveact_act_group_key"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lambing",
            name="completion_type",
            field=models.CharField(
                choices=[
                    ("normal", "Обычное завершение"),
                    ("early_failure", "Досрочно завершен"),
                    ("unsuccessful_insemination", "Неудачное осеменение"),
                ],
                db_index=True,
                default="normal",
                max_length=30,
                verbose_name="Тип завершения",
            ),
        ),
    ]
