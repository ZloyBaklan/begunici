import re

from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_safe

from begunici.app_types.inventory.models import Product, ProductPhoto


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
LAMB_NAME = re.compile(r"\bягн[её]н(?:ок|ка)\b|\bяген(?:ок|ка)\b", re.IGNORECASE)


def home(request):
    return render(request, "home.html")


def products(request, category="meat"):
    title, description = CATALOG_SECTIONS[category]
    cards = []
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
        cards.append({"product": product, "name": name, "photo_url": photo_url,
                      "image": f"img/products/{image}" if image else None})
    return render(request, "products.html", {"title": title, "description": description, "cards": cards})


@require_safe
def product_photo(request, pk, revision):
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
