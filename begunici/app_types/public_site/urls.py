from django.urls import path
from . import views
from .catalog_sync import receive_catalog

app_name = "public_site"

urlpatterns = [
    path('catalog-sync/', receive_catalog, name='catalog-sync'),
    path("", views.home, name="home"),
    path("products/", views.products, name="products"),
    path("products/photos/<int:pk>/<int:revision>/", views.product_photo, name="product-photo"),
    path("offal/", views.products, {"category": "offal"}, name="offal"),
    path("tribe/", views.tribe, name="tribe"),
    path("contacts/", views.contacts, name="contacts"),
]
