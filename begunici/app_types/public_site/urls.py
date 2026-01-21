from django.urls import path
from . import views

app_name = "public_site"

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.products, name="products"),
    path("contacts/", views.contacts, name="contacts"),
]
