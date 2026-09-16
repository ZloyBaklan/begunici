from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("animals", "0031_dashboardplanparameter"),
    ]

    operations = [
        migrations.CreateModel(
            name="TemporaryTag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tag_number", models.CharField(db_index=True, max_length=100, unique=True, verbose_name="Временная бирка")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="Создано")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Создал",
                    ),
                ),
            ],
            options={
                "verbose_name": "Временная бирка",
                "verbose_name_plural": "Временные бирки",
                "ordering": ["tag_number"],
            },
        ),
        migrations.AddField(
            model_name="maker",
            name="needs_retagging",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Животное включено в список на перебиркование.",
                verbose_name="Необходимо перебиркование",
            ),
        ),
        migrations.AddField(
            model_name="ram",
            name="needs_retagging",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Животное включено в список на перебиркование.",
                verbose_name="Необходимо перебиркование",
            ),
        ),
        migrations.AddField(
            model_name="ewe",
            name="needs_retagging",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Животное включено в список на перебиркование.",
                verbose_name="Необходимо перебиркование",
            ),
        ),
        migrations.AddField(
            model_name="sheep",
            name="needs_retagging",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Животное включено в список на перебиркование.",
                verbose_name="Необходимо перебиркование",
            ),
        ),
    ]
