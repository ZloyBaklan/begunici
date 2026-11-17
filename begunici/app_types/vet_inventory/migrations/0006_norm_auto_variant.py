from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("vet_inventory", "0005_product_base_name")]

    operations = [
        migrations.AddField(
            model_name="vetnorm", name="auto_variant",
            field=models.BooleanField(default=False),
        ),
    ]
