# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animals', '0011_add_date_otbivka_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='lambing',
            name='mother_tag_text',
            field=models.CharField(blank=True, help_text='Используется когда матери нет в БД', max_length=50, null=True, verbose_name='Бирка матери (текст)'),
        ),
        migrations.AddField(
            model_name='lambing',
            name='mother_type_text',
            field=models.CharField(blank=True, help_text='Овца/Ярка для матерей не в БД', max_length=20, null=True, verbose_name='Тип матери (текст)'),
        ),
    ]