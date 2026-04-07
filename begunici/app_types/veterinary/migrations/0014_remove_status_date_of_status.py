# Generated manually

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('veterinary', '0013_alter_placemovement_options_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='status',
            name='date_of_status',
        ),
    ]