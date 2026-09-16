from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0029_sheepbodyconditionrecord"),
    ]

    operations = [
        migrations.AlterField(
            model_name="archiveact",
            name="fatness",
            field=models.CharField(
                blank=True,
                choices=[
                    ("1", "1 - кахексия (истощение)"),
                    ("2", "2 - ниже средней"),
                    ("3", "3 - средняя"),
                    ("4", "4 - выше средней"),
                    ("5", "5 - высшая (ожирение)"),
                ],
                default="",
                max_length=20,
                verbose_name="Упитанность",
            ),
        ),
    ]
