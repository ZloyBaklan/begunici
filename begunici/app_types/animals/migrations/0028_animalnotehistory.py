from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("veterinary", "0019_remove_place_date_of_transfer"),
        ("animals", "0027_lambing_unsuccessful_insemination"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnimalNoteHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_note", models.TextField(blank=True, default="", verbose_name="Было")),
                ("new_note", models.TextField(blank=True, default="", verbose_name="Стало")),
                (
                    "change_date",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        verbose_name="Дата изменения",
                    ),
                ),
                (
                    "tag",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="note_history",
                        to="veterinary.tag",
                        verbose_name="Бирка",
                    ),
                ),
            ],
            options={
                "verbose_name": "История примечания",
                "verbose_name_plural": "История примечаний",
                "ordering": ["-change_date", "-id"],
            },
        ),
    ]
