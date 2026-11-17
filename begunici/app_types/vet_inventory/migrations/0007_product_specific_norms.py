from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("vet_inventory", "0006_norm_auto_variant")]

    operations = [
        migrations.AlterField(
            model_name="vetnorm", name="care",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name="stock_norms", to="veterinary.veterinarycare"),
        ),
        migrations.AddConstraint(
            model_name="vetnorm",
            constraint=models.UniqueConstraint(fields=("care", "product"), name="vet_unique_care_product_norm"),
        ),
    ]
