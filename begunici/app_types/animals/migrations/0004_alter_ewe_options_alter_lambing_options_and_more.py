# Generated by Django 4.2.15 on 2024-11-21 14:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('animals', '0003_alter_ewe_options_alter_ram_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='ewe',
            options={},
        ),
        migrations.AlterModelOptions(
            name='lambing',
            options={'ordering': ['id'], 'verbose_name': 'Окот', 'verbose_name_plural': 'Окоты'},
        ),
        migrations.AlterModelOptions(
            name='maker',
            options={'ordering': ['id'], 'verbose_name': 'Производитель', 'verbose_name_plural': 'Производители'},
        ),
        migrations.AlterModelOptions(
            name='ram',
            options={},
        ),
        migrations.AlterModelOptions(
            name='sheep',
            options={},
        ),
    ]