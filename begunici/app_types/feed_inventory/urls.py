from django.urls import path
from . import views

app_name = "feed_inventory"
urlpatterns = [
    path("", views.home, name="home"),
    path("orders/", views.orders, name="orders"),
    path("orders/<int:pk>/", views.order_detail, name="order"),
    path("orders/<int:order_id>/receive/", views.document_new, {"kind": "receipt"}, name="receive"),
    path("consume/", views.document_new, {"kind": "consume"}, name="consume"),
    path("writeoffs/", views.writeoffs, name="writeoffs"),
    path("writeoffs/new/", views.document_new, {"kind": "writeoff"}, name="writeoff-new"),
    path("versions/<int:pk>/act/", views.writeoff_print, name="writeoff-print"),
    path("documents/<int:pk>/", views.document_detail, name="document"),
    path("versions/<int:pk>/download/", views.version_download, name="download"),
    path("products/", views.products, name="products"),
    path("products/<int:pk>/edit/", views.product_edit, name="product-edit"),
    path("norms/", views.norms, name="norms"),
    path("plan.xlsx", views.export, name="export"),
    path("history/", views.history, name="history"),
]
