from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("veterinary", "0017_veterinarycare_type_class_structure"),
    ]

    operations = [
        migrations.AlterField(
            model_name="veterinarycare",
            name="care_type",
            field=models.CharField(
                choices=[
                    ("Вакцинация", "Вакцинация"),
                    ("Противопаразитарная", "Противопаразитарная"),
                    ("Прочее", "Прочее"),
                ],
                default="Вакцинация",
                max_length=100,
                verbose_name="Тип ветобработки",
            ),
        ),
        migrations.AlterField(
            model_name="veterinarycare",
            name="care_name",
            field=models.CharField(
                default="Иммунизация",
                max_length=200,
                verbose_name="Класс ветобработки",
            ),
        ),
    ]

