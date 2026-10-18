from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("animals", "0036_animal_rejection_history")]

    operations = [
        migrations.RemoveConstraint(
            model_name="animalrejectionhistory", name="reject_history_known_date",
        ),
        migrations.AlterField(
            model_name="animalrejectionhistory", name="source",
            field=models.CharField(
                choices=[
                    ("change", "Изменение отметки"),
                    ("log", "Восстановлено из лога"),
                    ("legacy", "Дата изменения неизвестна"),
                    ("manual", "Дата согласована пользователем"),
                ],
                default="change", max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name="animalrejectionhistory",
            constraint=models.CheckConstraint(
                check=(models.Q(source="legacy", change_date__isnull=True)
                       | (models.Q(source__in=["change", "log", "manual"])
                          & models.Q(change_date__isnull=False))),
                name="reject_history_known_date",
            ),
        ),
    ]
