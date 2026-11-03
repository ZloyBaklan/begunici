from django.urls import path
from . import views

app_name = "public_site"

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.products, name="products"),
    path("offal/", views.products, {"category": "offal"}, name="offal"),
    path("tribe/", views.tribe, name="tribe"),
    path("contacts/", views.contacts, name="contacts"),
]
