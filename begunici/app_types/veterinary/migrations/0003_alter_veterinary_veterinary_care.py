# Generated by Django 4.2.15 on 2024-12-23 12:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('veterinary', '0002_remove_veterinary_place_remove_veterinary_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='veterinary',
            name='veterinary_care',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='veterinary.veterinarycare', verbose_name='Вет-обработка'),
        ),
    ]
