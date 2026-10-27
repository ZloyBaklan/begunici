from django.db import migrations, models

from begunici.app_types.animals.dorper import recalculate_dorper_values


def recalculate_automatic_blood(apps, schema_editor):
    animal_models = tuple(apps.get_model("animals", name) for name in ("Maker", "Ram", "Ewe", "Sheep"))
    recalculate_dorper_values(animal_models, using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [("animals", "0041_lambing_tracked_veterinary")]

    operations = [
        migrations.AddField(
            model_name=name,
            name="dorper_uses_default",
            field=models.BooleanField(
                default=False, editable=False, verbose_name="Кровность рассчитана с допущением",
                help_text="В расчёте животного или его предков неизвестная кровность принята за 50%",
            ),
        ) for name in ("maker", "ram", "ewe", "sheep")
    ] + [migrations.RunPython(recalculate_automatic_blood, migrations.RunPython.noop)]
