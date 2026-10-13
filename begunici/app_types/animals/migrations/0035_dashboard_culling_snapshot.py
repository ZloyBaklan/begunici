from django.db import migrations, models
from django.utils import timezone


def capture_initial_population(apps, schema_editor):
    alias = schema_editor.connection.alias
    sheep = apps.get_model('animals', 'Sheep')
    snapshot = apps.get_model('animals', 'DashboardCullingSnapshot')
    counts = sheep.objects.using(alias).filter(is_archived=False).aggregate(
        active_sheep_count=models.Count('pk'),
        rejected_sheep_count=models.Count('pk', filter=models.Q(is_reject=True)),
    )
    snapshot.objects.using(alias).create(recorded_at=timezone.now(), **counts)


class Migration(migrations.Migration):
    dependencies = [('animals', '0034_animal_is_for_sale')]

    operations = [
        migrations.CreateModel(
            name='DashboardCullingSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recorded_at', models.DateTimeField(db_index=True, default=timezone.now)),
                ('active_sheep_count', models.PositiveIntegerField()),
                ('rejected_sheep_count', models.PositiveIntegerField()),
            ],
            options={'ordering': ['recorded_at', 'id']},
        ),
        migrations.RunPython(capture_initial_population, migrations.RunPython.noop),
    ]
