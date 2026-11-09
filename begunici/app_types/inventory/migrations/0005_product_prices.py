from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0004_product_catalog")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="unit_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True,
                                      validators=[MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name="product",
            name="price_unit",
            field=models.CharField(choices=[("kg", "кг"), ("pcs", "шт.")], default="kg", max_length=3),
        ),
    ]
