"""Fresh sandbox compatibility for an existing duplicate field in migration 0002."""
from importlib import import_module
from django.conf import settings
from django.test.runner import DiscoverRunner
from django.db import connection


def baseline_migrations():
    if settings.DATABASES["default"]["NAME"] not in {"clinical_sandbox", "test_clinical_sandbox"}:
        raise RuntimeError("Baseline compatibility is limited to disposable clinical databases.")
    module = import_module("begunici.app_types.animals.migrations.0002_alter_ewe_options_alter_ram_options_and_more")
    # planned_lambing_date already exists in 0001_initial in current main.
    module.Migration.operations = [op for op in module.Migration.operations if getattr(op, "name", "") != "planned_lambing_date"]


class IsolatedRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        baseline_migrations()
        result = super().setup_databases(**kwargs)
        complete_sandbox_schema()
        return result


def complete_sandbox_schema():
    if connection.settings_dict["NAME"] not in {"clinical_sandbox", "test_clinical_sandbox"}:
        raise RuntimeError("Only disposable clinical databases can be adapted.")
    from begunici.app_types.animals.models import Sheep
    with connection.cursor() as cursor:
        columns = {col.name for col in connection.introspection.get_table_description(cursor, Sheep._meta.db_table)}
    if "planned_lambing_date" not in columns:
        with connection.schema_editor() as editor:
            editor.add_field(Sheep, Sheep._meta.get_field("planned_lambing_date"))
