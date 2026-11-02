from django.apps import AppConfig


class ClinicalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "begunici.app_types.clinical"
    verbose_name = "Лечение/Карантин"

    def ready(self):
        from . import bridge  # noqa: F401
