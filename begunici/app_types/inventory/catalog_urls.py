from django.urls import path
from . import catalog_views

app_name = "inventory_catalog"
urlpatterns = [
    path("meat/", catalog_views.meat_products, name="meat-products"),
    path("meat/<int:pk>/", catalog_views.meat_products, name="meat-product-edit"),
    path("feeds/", catalog_views.feed_products, name="feed-products"),
    path("feeds/<int:pk>/", catalog_views.feed_products, name="feed-product-edit"),
]
