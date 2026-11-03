import re

from django.shortcuts import render

from begunici.app_types.inventory.models import Product


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
    for product in Product.objects.filter(category=category):
        if LAMB_NAME.search(product.name):
            name = LAMB_NAME.sub("ягнёнка", product.name)
            if not re.search(r"\bпремиум\b", name, re.IGNORECASE):
                name += " премиум"
        else:
            name = f"{product.name} ягнёнка"
        image = PRODUCT_IMAGES.get(product.code)
        cards.append({"product": product, "name": name, "image": f"img/products/{image}" if image else None})
    return render(request, "products.html", {"title": title, "description": description, "cards": cards})


def tribe(request):
    return render(request, "tribe.html")


def contacts(request):
    return render(request, "contacts.html")
