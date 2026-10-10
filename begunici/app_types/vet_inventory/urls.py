from django.urls import path
from . import views

app_name = "vet_inventory"
urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.products, name="products"),
    path("products/<int:pk>/edit/", views.product_edit, name="product-edit"),
    path("orders/", views.orders, name="orders"),
    path("orders/<int:pk>/", views.order_detail, name="order"),
    path("orders/<int:order_id>/receive/", views.document_new, {"kind": "receipt"}, name="receive"),
    path("consume/", views.document_new, {"kind": "consume"}, name="consume"),
    path("writeoffs/", views.writeoffs, name="writeoffs"),
    path("writeoffs/new/", views.document_new, {"kind": "writeoff"}, name="writeoff-new"),
    path("documents/<int:pk>/", views.document_detail, name="document"),
    path("versions/<int:pk>/download/", views.version_download, name="download"),
    path("versions/<int:pk>/act/", views.writeoff_print, name="writeoff-print"),
    path("norms/", views.norms, name="norms"),
    path("norms/<int:pk>/", views.norm_edit, name="norm-edit"),
    path("treatments/", views.treatment_list, name="treatments"),
    path("treatments/<int:pk>/", views.treatment_detail, name="treatment"),
    path("history/", views.history, name="history"),
]
