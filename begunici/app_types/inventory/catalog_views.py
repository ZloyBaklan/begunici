from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .catalog_management import ProductForm, product_used, product_values, save_product
from .models import Product
from .permissions import can_edit_meat_catalog, require_meat_catalog_editor


@require_http_methods(["GET", "POST"])
def meat_products(request, pk=None):
    can_edit = can_edit_meat_catalog(request.user)
    if request.method == "POST" or pk is not None:
        require_meat_catalog_editor(request.user)
    products = Product.objects.exclude(category="live")
    if can_edit:
        products = products.select_related("storefront_photo").defer("storefront_photo__content")
    product = get_object_or_404(products, pk=pk) if pk else None
    form_data = (request.POST, request.FILES) if request.method == "POST" else ()
    form = ProductForm(*form_data, initial=product_values(product) if product else None)
    used = product_used(product) if product else False
    if used:
        form.fields["category"].disabled = True
        form.fields["unit"].disabled = True
    if request.method == "POST" and form.is_valid():
        try:
            save_product(request.user, form.cleaned_data, pk)
            request._inventory_logged = True
            messages.success(request, "Номенклатура сохранена. Она доступна в складском учёте, СП-55 и накладных.")
            return redirect("inventory_catalog:meat-products")
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Позиция уже изменилась. Обновите страницу.")
    if request.method == "POST":
        request._stock_audit_error = "; ".join(
            f"{form.fields[name].label}: {error}" if name in form.fields else str(error)
            for name, errors in form.errors.items() for error in errors
        )
    return render(request, "inventory/catalog/products.html", {"form": form, "product": product,
        "unit_locked": used, "can_edit": can_edit,
        "products": products})


def feed_products(request, pk=None):
    from begunici.app_types.feed_inventory import views
    return views.product_edit(request, pk, catalog_mode=True) if pk else views.products(request, catalog_mode=True)
