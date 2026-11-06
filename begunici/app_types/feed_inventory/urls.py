from django.urls import path
from . import views
from . import barn_views
from . import map_operations
from . import map_closing

app_name = "feed_inventory"
urlpatterns = [
    path("barns/", barn_views.overview, name="barns"),
    path("barns/data/", barn_views.map_data, name="barn-data"),
    path("barns/map-operation/", map_operations.save, name="map-operation"),
    path("barns/map-closing/", map_closing.details, name="map-closing"),
    path("barns/analytics/", barn_views.analytics, name="analytics"),
    path("barns/files/<int:pk>/", barn_views.attachment, name="barn-file"),
    path("barns/<int:barn>/", barn_views.detail, name="barn"),
    path("barns/<int:barn>/close/", barn_views.close, name="barn-close"),
    path("barns/<int:barn>/<str:kind>/", barn_views.move, name="barn-move"),
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
