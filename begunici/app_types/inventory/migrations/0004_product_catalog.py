from django.db import migrations, models


def seed(apps, schema_editor):
    product = apps.get_model("inventory", "Product")
    product.objects.get_or_create(code="tongue", defaults={"name": "Язык", "category": "offal", "counted": True})
    limits = {"carcass": 1, "half": 2, "tenderloin": 2, "shoulder": 2,
              "side": 2, "rack": 2, "shank": 4, "leg": 2, "ribs": 2,
              "liver": 1, "kidneys": 2, "testes": 2, "head": 1, "heart": 1, "tongue": 1}
    for code, maximum in limits.items():
        product.objects.filter(code=code).update(parts_per_animal=maximum)


class Migration(migrations.Migration):
    dependencies = [("inventory", "0003_orderline_animal_type")]
    operations = [
        migrations.AddField(model_name="product", name="parts_per_animal", field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="product", name="revision", field=models.PositiveIntegerField(default=1)),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
