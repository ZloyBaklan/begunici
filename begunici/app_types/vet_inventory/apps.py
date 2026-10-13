from django.apps import AppConfig


class VetInventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "begunici.app_types.vet_inventory"
    verbose_name = "Склад ветпрепаратов"

    def ready(self):
        from . import bridge  # noqa: F401
