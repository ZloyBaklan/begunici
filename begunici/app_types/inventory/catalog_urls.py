from django.urls import path
from . import catalog_views
from begunici.app_types.vet_inventory import views as vet_catalog_views

app_name = "inventory_catalog"
urlpatterns = [
    path("vet/", vet_catalog_views.products, name="vet-products"),
    path("vet/<int:pk>/", vet_catalog_views.product_edit, name="vet-product-edit"),
    path("meat/", catalog_views.meat_products, name="meat-products"),
    path("meat/<int:pk>/", catalog_views.meat_products, name="meat-product-edit"),
    path("feeds/", catalog_views.feed_products, name="feed-products"),
    path("feeds/<int:pk>/", catalog_views.feed_products, name="feed-product-edit"),
]
