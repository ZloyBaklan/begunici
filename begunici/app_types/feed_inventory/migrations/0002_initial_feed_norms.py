from django.db import migrations

from begunici.app_types.feed_inventory.defaults import GROUPS, PRODUCTS


def seed(apps, schema_editor):
    database = schema_editor.connection.alias
    settings = apps.get_model("feed_inventory", "FeedSettings")
    product_model = apps.get_model("feed_inventory", "FeedProduct")
    norm_model = apps.get_model("feed_inventory", "FeedNorm")
    settings.objects.using(database).get_or_create(pk=1)
    for name, category, package, rates in PRODUCTS:
        product = product_model.objects.using(database).create(name=name, category=category, unit="kg", package=package)
        for group, rate in zip(GROUPS, rates):
            norm_model.objects.using(database).create(product=product, group=group, per_head=rate)


class Migration(migrations.Migration):
    dependencies = [("feed_inventory", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
