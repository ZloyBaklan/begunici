from django.urls import path

from . import views

app_name = "inventory"
urlpatterns = [
    path("", views.dashboard, name="home"),
    path("live/", views.dashboard, {"section": "live"}, name="live"),
    path("pending/", views.dashboard, {"section": "pending"}, name="pending"),
    path("stock/", views.dashboard, {"section": "stock"}, name="stock"),
    path("archive/", views.dashboard, {"section": "archive"}, name="archive"),
    path("sp55/", views.slaughter, name="slaughter"),
    path("animals/<int:tag_id>/", views.animal, name="animal"),
    path("documents/<int:pk>/", views.document, name="document"),
    path("documents/<int:pk>/versions/<int:number>/", views.version_download, name="download"),
    path("invoices/new/", views.invoice_new, name="invoice-new"),
    path("orders/", views.order_list, name="orders"),
    path("orders/new/", views.order_new, name="order-new"),
    path("orders/<int:pk>/", views.order_detail, name="order"),
    path("lots/<int:pk>/cut/", views.cut_page, name="cut"),
    path("api/receipts/prepare/", views.receipt_prepare_api, name="receipt-prepare"),
    path("api/receipts/<int:pk>/save/", views.receipt_save_api, name="receipt-save"),
    path("api/documents/<int:pk>/confirm/", views.confirm_api, name="confirm"),
    path("api/documents/<int:pk>/replace/", views.replace_file_api, name="replace"),
    path("api/documents/<int:pk>/return/", views.return_to_vet_api, name="return"),
    path("api/invoices/save/", views.invoice_save_api, name="invoice-save"),
    path("api/invoices/<int:pk>/reverse/", views.reverse_api, name="reverse"),
    path("api/orders/create/", views.order_create_api, name="order-create"),
    path("api/orders/<int:pk>/close/", views.order_close_api, name="order-close"),
    path("api/lots/<int:pk>/cut/", views.cut_api, name="cut-api"),
]
