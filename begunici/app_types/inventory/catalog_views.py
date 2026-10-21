from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .catalog_management import ProductForm, product_used, product_values, save_product
from .models import Product
from .permissions import access_required


@require_http_methods(["GET", "POST"])
@access_required()
def meat_products(request, pk=None):
    product = get_object_or_404(Product.objects.exclude(category="live"), pk=pk) if pk else None
    form = ProductForm(request.POST if request.method == "POST" else None,
                       initial=product_values(product) if product else None)
    used = product_used(product) if product else False
    if used:
        form.fields["category"].disabled = True
        form.fields["unit"].disabled = True
    if request.method == "POST" and form.is_valid():
        try:
            save_product(request.user, form.cleaned_data, pk)
            messages.success(request, "Номенклатура сохранена. Она доступна в складском учёте, СП-55 и накладных.")
            return redirect("inventory_catalog:meat-products")
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Позиция уже изменилась. Обновите страницу.")
    return render(request, "inventory/catalog/products.html", {"form": form, "product": product,
        "unit_locked": used,
        "products": Product.objects.exclude(category="live")})


def feed_products(request, pk=None):
    from begunici.app_types.feed_inventory import views
    return views.product_edit(request, pk, catalog_mode=True) if pk else views.products(request, catalog_mode=True)
