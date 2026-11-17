from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("vet_inventory", "0007_product_specific_norms")]

    operations = [
        migrations.RemoveField(model_name="vetproduct", name="package"),
    ]
