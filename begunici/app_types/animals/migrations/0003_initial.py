# Generated manually to fix duplicate key constraint issue
# This migration removes the redundant unique=True constraint from the tag field
# in AnimalBase model, as OneToOneField already enforces uniqueness

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('veterinary', '0002_alter_place_date_of_transfer_and_more'),
        ('animals', '0002_alter_ewe_options_alter_ram_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ewe',
            name='tag',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                to='veterinary.tag',
                verbose_name='Бирка'
            ),
        ),
        migrations.AlterField(
            model_name='maker',
            name='tag',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                to='veterinary.tag',
                verbose_name='Бирка'
            ),
        ),
        migrations.AlterField(
            model_name='ram',
            name='tag',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                to='veterinary.tag',
                verbose_name='Бирка'
            ),
        ),
        migrations.AlterField(
            model_name='sheep',
            name='tag',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                to='veterinary.tag',
                verbose_name='Бирка'
            ),
        ),
    ]
