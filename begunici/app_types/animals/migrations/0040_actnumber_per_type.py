from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("animals", "0039_actnumber")]

    operations = [
        migrations.RemoveConstraint(
            model_name="actnumber", name="act_number_month_sequence_unique"
        ),
        migrations.AddConstraint(
            model_name="actnumber",
            constraint=models.UniqueConstraint(
                fields=("source_type", "period", "sequence"),
                name="act_number_type_month_unique",
            ),
        ),
    ]
