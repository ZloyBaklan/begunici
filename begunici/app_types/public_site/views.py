import re

from django.conf import settings
from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_safe

from begunici.app_types.inventory.models import Product, ProductPhoto
from .models import CatalogPhoto, CatalogProduct


CATALOG_SECTIONS = {
    "meat": ("Мясная продукция", "Мясо ягнёнка с фермы «Бегуницы» для запекания, гриля и домашних блюд."),
    "offal": ("Субпродукты", "Субпродукты ягнёнка с фермы «Бегуницы» для бульонов, паштетов и горячих блюд."),
}
PRODUCT_IMAGES = {
    "tenderloin": "cut.png",
    "shoulder": "shoulder_blade.png",
    "mince": "mincemeat.png",
    "side": "side_of_lamb.png",
    "rack": "rack_of_lamb.png",
    "steak": "stake.png",
}
PRODUCT_PACKAGING = {
    "tenderloin": "700 г",
    "mince": "500 г",
    "side": "1100–1300 г",
    "rack": "600–800 г за штуку",
    "steak": "170–220 г",
}
PRODUCT_DESCRIPTIONS = {
    "carcass": "Целая туша для разделки на отрубы или запекания на вертеле.",
    "half": "Половина туши для разделки на порции и приготовления нескольких блюд.",
    "tenderloin": "Нежная вырезка для быстрой обжарки на сковороде или гриле.",
    "shoulder": "Лопатка подходит для медленного запекания и тушения с овощами.",
    "mince": "Фарш для домашних котлет, люля-кебаба и начинки.",
    "side": "Бок ягнёнка подходит для запекания целым куском или рулетом.",
    "rack": "Каре на кости можно запечь целиком или нарезать на порционные котлеты.",
    "steak": "Порционный стейк для быстрой обжарки на сковороде или гриле.",
    "shank": "Голень становится мягкой при длительном тушении с травами.",
    "leg": "Окорок для запекания целым куском и подачи к общему столу.",
    "ribs": "Рёбра можно запечь со специями или приготовить на гриле.",
    "lungs": "Лёгкие можно отварить для начинки или потушить с овощами.",
    "liver": "Печень подходит для быстрой обжарки с луком и для паштетов.",
    "kidneys": "Почки можно потушить в соусе или использовать в начинке.",
    "testes": "Семенники подойдут для быстрой обжарки со специями.",
    "head": "Голова подходит для наваристого бульона и традиционных блюд.",
    "heart": "Сердце хорошо подходит для длительного тушения с овощами.",
    "tongue": "Язык можно отварить и подать как холодную закуску.",
}
DEFAULT_DESCRIPTIONS = {
    "meat": "Уточним особенности отруба и подскажем, как его приготовить.",
    "offal": "Подскажем, как подготовить этот субпродукт и для каких блюд он подходит.",
}
LAMB_NAME = re.compile(r"\bягн[её]н(?:ок|ка)\b|\bяген(?:ок|ка)\b", re.IGNORECASE)


def home(request):
    return render(request, "home.html")


def products(request, category="meat"):
    title, description = CATALOG_SECTIONS[category]
    cards = []
    if settings.APP_MODE == 'public':
        catalog = CatalogProduct.objects.filter(category=category).annotate(
            has_photo=Exists(CatalogPhoto.objects.filter(pk=OuterRef('photo_id'))),
        )
    else:
        catalog = Product.objects.filter(category=category).annotate(
            has_photo=Exists(ProductPhoto.objects.filter(product_id=OuterRef("pk"))),
        )
    for product in catalog:
        if product.storefront_name:
            name = product.storefront_name
        elif LAMB_NAME.search(product.name):
            name = LAMB_NAME.sub("ягнёнка", product.name)
            if not re.search(r"\bпремиум\b", name, re.IGNORECASE):
                name += " премиум"
        else:
            name = f"{product.name} ягнёнка"
        image = PRODUCT_IMAGES.get(product.code)
        photo_url = None
        if product.has_photo:
            photo_url = reverse("public_site:product-photo", args=[product.pk, product.revision])
        cards.append({
            "product": product, "name": name, "photo_url": photo_url,
            "image": f"img/products/{image}" if image else None,
            "packaging": PRODUCT_PACKAGING.get(product.code, "уточняйте"),
            "description": PRODUCT_DESCRIPTIONS.get(product.code, DEFAULT_DESCRIPTIONS[category]),
        })
    cards.sort(key=lambda card: not (card["photo_url"] or card["image"]))
    return render(request, "products.html", {"title": title, "description": description, "cards": cards})


@require_safe
def product_photo(request, pk, revision):
    if settings.APP_MODE == 'public':
        product = get_object_or_404(CatalogProduct.objects.select_related('photo'),
                                   pk=pk, revision=revision, photo__isnull=False,
                                   category__in=CATALOG_SECTIONS)
        photo = product.photo
    else:
        photo = get_object_or_404(ProductPhoto, product_id=pk, product__revision=revision,
                                  product__category__in=CATALOG_SECTIONS)
    response = HttpResponse(bytes(photo.content), content_type=photo.content_type)
    response["Cache-Control"] = "public, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def tribe(request):
    return render(request, "tribe.html")


def contacts(request):
    return render(request, "contacts.html")
