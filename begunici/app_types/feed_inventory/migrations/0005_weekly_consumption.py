from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("feed_inventory", "0004_packaging_and_barn_ledger")]

    operations = [
        migrations.AlterField(
            model_name="barnfeeddocument",
            name="kind",
            field=models.CharField(max_length=12, choices=[
                ("delivery", "Поставка"), ("return", "Возврат на склад"), ("writeoff", "Списание по акту"),
                ("week", "Расход за неделю"), ("close", "Факт за месяц"), ("reversal", "Сторно"),
            ]),
        ),
    ]
