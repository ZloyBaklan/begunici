from django.db import migrations


def seed(apps, schema_editor):
    product = apps.get_model("inventory", "Product")
    # Frozen migration data: never import the editable runtime catalogue here.
    entries = [
        ("live", "Живое животное", "live", True),
        ("carcass", "Туша", "meat", True), ("half", "Полутуша", "meat", True),
        ("tenderloin", "Вырезка ягнёнка", "meat", True),
        ("shoulder", "Лопатка ягнёнка", "meat", True),
        ("mince", "Фарш ягнёнка", "meat", False),
        ("side", "Бок ягнёнка", "meat", True),
        ("rack", "Каре ягнёнка", "meat", True),
        ("steak", "Стейк ягнёнка", "meat", True),
        ("shank", "Голень", "meat", True), ("leg", "Окорок", "meat", True),
        ("ribs", "Рёбра", "meat", True), ("lungs", "Лёгкие", "offal", True),
        ("liver", "Печень", "offal", True), ("kidneys", "Почки", "offal", True),
        ("testes", "Семенники", "offal", True), ("head", "Голова", "offal", True),
        ("heart", "Сердце", "offal", True),
    ]
    for code, name, category, counted in entries:
        product.objects.get_or_create(code=code, defaults={"name": name, "category": category, "counted": counted})


class Migration(migrations.Migration):
    dependencies = [("inventory", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
