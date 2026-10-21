"""One catalog for technical information, slaughter acts and warehouse forms."""
import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import AuditEvent, Document, DocumentVersion, Product
from .permissions import require_inventory


class ProductForm(forms.Form):
    revision = forms.IntegerField(required=False, widget=forms.HiddenInput)
    name = forms.CharField(label="Название", max_length=120)
    category = forms.ChoiceField(label="Категория", choices=[("meat", "Мясная часть"), ("offal", "Субпродукт")])
    unit = forms.ChoiceField(label="Единицы учёта", choices=[("kg_pcs", "кг и шт."), ("kg", "кг (только вес)")])
    parts_per_animal = forms.IntegerField(label="Максимум штук с одного животного", min_value=1, max_value=1000, required=False,
        help_text="Для весовой продукции оставьте пустым.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean(self):
        values = super().clean()
        if values.get("unit") == "kg" and values.get("parts_per_animal"):
            self.add_error("parts_per_animal", "Для весовой продукции ограничение штук не задаётся.")
        return values


def product_used(product):
    if product.stocklot_set.exists() or product.orderline_set.exists():
        return True
    for collection in (Document.objects.values_list("payload__outputs", flat=True),
                       DocumentVersion.objects.values_list("snapshot__payload__outputs", flat=True)):
        if any(any(row.get("product") == product.code for row in (lines or [])) for lines in collection.iterator()):
            return True
    return False


def product_values(product):
    return {"revision": product.revision, "name": product.name, "category": product.category,
            "unit": "kg_pcs" if product.counted else "kg", "parts_per_animal": product.parts_per_animal}


@transaction.atomic
def save_product(user, values, pk=None):
    require_inventory(user)
    # Use the same lock order as receipt/order/cutting commands: changing an
    # unused unit cannot race its first use in an accounting document.
    list(Product.objects.select_for_update().order_by("pk"))
    product = Product.objects.select_for_update().get(pk=pk) if pk else Product(code="item-" + uuid.uuid4().hex)
    if pk and str(product.revision) != str(values.get("revision")):
        raise ValidationError("Номенклатура уже изменена. Обновите страницу.")
    if product.category == "live":
        raise ValidationError("Системная позиция живого животного не редактируется здесь.")
    name = values["name"].strip()
    if any(other.casefold() == name.casefold() for other in Product.objects.exclude(pk=pk).values_list("name", flat=True)):
        raise ValidationError("Позиция с таким названием уже есть в номенклатуре.")
    before = product_values(product) if pk else None
    counted = values["unit"] == "kg_pcs"
    maximum = values.get("parts_per_animal")
    if product.code in {"carcass", "half"} and (not counted or values["category"] != "meat" or maximum != (1 if product.code == "carcass" else 2)):
        raise ValidationError("Туша и полутуша сохраняют мясную категорию, учёт в кг и штуках и предел 1 / 2.")
    if pk and product_used(product) and (product.counted != counted or product.category != values["category"]):
        raise ValidationError("Единицы и категория уже используются в учёте. Для другого способа учёта добавьте отдельную позицию.")
    product.name, product.category, product.counted = name, values["category"], counted
    product.parts_per_animal = maximum
    if pk:
        product.revision += 1
    product.full_clean()
    product.save()
    AuditEvent.objects.create(actor=user, action="product_updated" if pk else "product_created",
        data={"product": product.pk, "before": before, "after": product_values(product)})
    return product
