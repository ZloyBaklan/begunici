# Generated by Django 4.2.15 on 2024-09-18 10:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('animals', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='maker',
            name='name',
        ),
        migrations.AddField(
            model_name='ewe',
            name='note',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Примечание'),
        ),
        migrations.AddField(
            model_name='maker',
            name='note',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Примечание'),
        ),
        migrations.AddField(
            model_name='ram',
            name='note',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Примечание'),
        ),
        migrations.AddField(
            model_name='sheep',
            name='note',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Примечание'),
        ),
    ]
