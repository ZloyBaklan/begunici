"""One catalog for technical information, slaughter acts and warehouse forms."""
import uuid
from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from PIL import Image

from .models import AuditEvent, Document, DocumentVersion, Product, ProductPhoto
from .permissions import require_meat_catalog_editor


PHOTO_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_PHOTO_SIZE = 5 * 1024 * 1024
MAX_PHOTO_PIXELS = 25_000_000


class ProductForm(forms.Form):
    revision = forms.IntegerField(required=False, widget=forms.HiddenInput)
    name = forms.CharField(label="Название", max_length=120)
    storefront_name = forms.CharField(
        label="Название на сайте", max_length=120, required=False,
        help_text="Если поле пустое, название карточки формируется из складского названия.",
    )
    photo = forms.FileField(
        label="Фотография для сайта", required=False,
        widget=forms.FileInput(attrs={"accept": ",".join(PHOTO_FORMATS.values())}),
        help_text="JPEG, PNG или WebP до 5 МБ. Чтобы заменить фото, выберите новый файл.",
    )
    category = forms.ChoiceField(label="Категория", choices=[("meat", "Мясная часть"), ("offal", "Субпродукт")])
    unit = forms.ChoiceField(label="Единицы учёта", choices=[("kg_pcs", "кг и шт."), ("kg", "кг (только вес)")])
    parts_per_animal = forms.IntegerField(label="Максимум штук с одного животного", min_value=1, max_value=1000, required=False,
        help_text="Для весовой продукции оставьте пустым.")
    unit_price = forms.DecimalField(label="Цена за единицу, ₽", min_value=0, max_digits=10,
                                    decimal_places=2, required=False)
    price_unit = forms.ChoiceField(label="Единица цены", choices=Product.PriceUnit.choices,
                                   initial=Product.PriceUnit.KG, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages.update({
                "required": "Это поле обязательно для заполнения.",
                "invalid": "Укажите корректное значение.",
                "invalid_choice": "Выберите значение из списка.",
                "min_value": "Укажите число не меньше %(limit_value)s.",
                "max_value": "Укажите число не больше %(limit_value)s.",
                "max_length": "Введите не более %(limit_value)s символов.",
            })
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean_photo(self):
        upload = self.cleaned_data["photo"]
        if upload is None:
            return None
        if upload.size > MAX_PHOTO_SIZE:
            raise ValidationError("Размер фотографии не должен превышать 5 МБ.")
        content = upload.read()
        try:
            with Image.open(BytesIO(content), formats=tuple(PHOTO_FORMATS)) as image:
                if image.width * image.height > MAX_PHOTO_PIXELS:
                    raise ValidationError("Разрешение фотографии не должно превышать 25 мегапикселей.")
                image.load()
                content_type = PHOTO_FORMATS[image.format]
        except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
            raise ValidationError("Загрузите корректное изображение JPEG, PNG или WebP.") from exc

        basename = upload.name.replace("\\", "/").rsplit("/", 1)[-1]
        filename = "".join(char for char in basename if char.isprintable())
        return {"filename": filename or "photo", "content_type": content_type, "content": content}

    def clean(self):
        values = super().clean()
        values["price_unit"] = values.get("price_unit") or self.initial.get("price_unit", Product.PriceUnit.KG)
        for name in ("unit_price", "storefront_name"):
            if name not in self.data and name in self.initial:
                values[name] = self.fields[name].clean(self.initial[name])
        if values.get("unit") == "kg" and values.get("parts_per_animal"):
            self.add_error("parts_per_animal", "Для весовой продукции ограничение штук не задаётся.")
        if values.get("unit") == "kg" and values.get("price_unit") == Product.PriceUnit.PIECE:
            self.add_error("price_unit", "Для весовой продукции задайте цену за килограмм.")
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
            "unit": "kg_pcs" if product.counted else "kg", "parts_per_animal": product.parts_per_animal,
            "unit_price": str(product.unit_price) if product.unit_price is not None else None,
            "price_unit": product.price_unit, "storefront_name": product.storefront_name}


@transaction.atomic
def save_product(user, values, pk=None):
    require_meat_catalog_editor(user)
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
    if before is not None:
        before["photo_filename"] = ProductPhoto.objects.filter(product_id=pk).values_list("filename", flat=True).first()
    counted = values["unit"] == "kg_pcs"
    maximum = values.get("parts_per_animal")
    if product.code in {"carcass", "half"} and (not counted or values["category"] != "meat" or maximum != (1 if product.code == "carcass" else 2)):
        raise ValidationError("Туша и полутуша сохраняют мясную категорию, учёт в кг и штуках и предел 1 / 2.")
    if pk and product_used(product) and (product.counted != counted or product.category != values["category"]):
        raise ValidationError("Единицы и категория уже используются в учёте. Для другого способа учёта добавьте отдельную позицию.")
    product.name, product.category, product.counted = name, values["category"], counted
    product.parts_per_animal = maximum
    product.unit_price = values.get("unit_price", product.unit_price)
    product.price_unit = values.get("price_unit", product.price_unit)
    product.storefront_name = values.get("storefront_name", product.storefront_name)
    if not counted and product.price_unit == Product.PriceUnit.PIECE:
        raise ValidationError("Для весовой продукции задайте цену за килограмм.")
    if pk:
        product.revision += 1
    product.full_clean()
    product.save()
    after = product_values(product)
    photo = values.get("photo")
    if photo:
        ProductPhoto.objects.update_or_create(product=product, defaults=photo)
        after["photo_filename"] = photo["filename"]
    else:
        after["photo_filename"] = before["photo_filename"] if before is not None else None
    AuditEvent.objects.create(actor=user, action="product_updated" if pk else "product_created",
        data={"product": product.pk, "before": before, "after": after})
    return product
