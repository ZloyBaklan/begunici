from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from .views import (
    MakerViewSet,
    MakersView,
    MakerDetailView,
    MakerAnalyticsView,
    RamViewSet,
    EweViewSet,
    SheepViewSet,
    LambingViewSet,
    animals,
    create_animal,
    ArchiveViewSet,
    RamDetailView,
    EweDetailView,
    SheepDetailView,
)

# Создаем маршруты для ViewSet
router = DefaultRouter()
router.register(r"maker", MakerViewSet)  # Маршрут для производителей
router.register(r"ram", RamViewSet)  # Маршрут для баранов
router.register(r"ewe", EweViewSet)  # Маршрут для ярок
router.register(r"sheep", SheepViewSet)  # Маршрут для овец
router.register(r"lambing", LambingViewSet)  # Маршрут для окотов
router.register(r"archive", ArchiveViewSet, basename="archive")  # Архив животных

# Подключаем router для управления всеми ViewSet
urlpatterns = [
    path(
        "maker/<str:tag_number>/info/", MakerDetailView.as_view(), name="maker-detail"
    ),
    path(
        "makers/<str:tag_number>/analytics/",
        MakerAnalyticsView.as_view(),
        name="maker-analytics",
    ),
    path(
        "ram/<str:tag_number>/info/", RamDetailView.as_view(), name="ram-detail"
    ),
    path(
        "ewe/<str:tag_number>/info/", EweDetailView.as_view(), name="ewe-detail"
    ),
    path(
        "sheep/<str:tag_number>/info/", SheepDetailView.as_view(), name="sheep-detail"
    ),
    path(
        "main_archive/",
        TemplateView.as_view(template_name="archive.html"),
        name="main_archive",
    ),
    path("", include(router.urls)),
    path(
        "maker/<str:tag_number>/api/",
        MakerViewSet.as_view({"get": "retrieve_api"}),
        name="maker-api",
    ),
    path(
        "ram/<str:tag_number>/api/",
        RamViewSet.as_view({"get": "retrieve"}),
        name="ram-api",
    ),
    path(
        "ewe/<str:tag_number>/api/",
        EweViewSet.as_view({"get": "retrieve"}),
        name="ewe-api",
    ),
    path(
        "sheep/<str:tag_number>/api/",
        SheepViewSet.as_view({"get": "retrieve"}),
        name="sheep-api",
    ),
    path(
        "maker/<str:tag_number>/update_parents/",
        MakerViewSet.as_view({"patch": "update_parents"}),
        name="update-parents",
    ),
    path(
        "ram/<str:tag_number>/update_parents/",
        RamViewSet.as_view({"patch": "update_parents"}),
        name="update-ram-parents",
    ),
    path(
        "ewe/<str:tag_number>/update_parents/",
        EweViewSet.as_view({"patch": "update_parents"}),
        name="update-ewe-parents",
    ),
    path(
        "sheep/<str:tag_number>/update_parents/",
        SheepViewSet.as_view({"patch": "update_parents"}),
        name="update-sheep-parents",
    ),
    # path('maker/<int:pk>/weight_history/', MakerViewSet.as_view({'get': 'weight_history'}), name='weight-history'),
    # path('maker/<int:pk>/add_weight/', MakerViewSet.as_view({'post': 'add_weight'}), name='add-weight'),
    # path('maker/<int:pk>/vet_history/', MakerViewSet.as_view({'get': 'vet_history'}), name='vet-history'),
    # path('maker/<int:pk>/place_history/', MakerViewSet.as_view({'get': 'place_history'}), name='place-history'),
    # path('maker/place_movement/', MakerViewSet.as_view({'post': 'add_place_movement'}), name='add-place-movement'),
    path(
        "maker/<str:tag_number>/children/",
        MakerViewSet.as_view({"get": "children"}),
        name="maker-children",
    ),
    path(
        "ram/<str:tag_number>/children/",
        RamViewSet.as_view({"get": "children"}),
        name="ram-children",
    ),
    path(
        "ewe/<str:tag_number>/children/",
        EweViewSet.as_view({"get": "children"}),
        name="ewe-children",
    ),
    path(
        "sheep/<str:tag_number>/children/",
        SheepViewSet.as_view({"get": "children"}),
        name="sheep-children",
    ),
    path(
        "maker/<str:tag_number>/status_history/",
        MakerViewSet.as_view({"get": "status_history"}),
        name="maker-status-history",
    ),
    path(
        "ram/<str:tag_number>/status_history/",
        RamViewSet.as_view({"get": "status_history"}),
        name="ram-status-history",
    ),
    path(
        "ewe/<str:tag_number>/status_history/",
        EweViewSet.as_view({"get": "status_history"}),
        name="ewe-status-history",
    ),
    path(
        "sheep/<str:tag_number>/status_history/",
        SheepViewSet.as_view({"get": "status_history"}),
        name="sheep-status-history",
    ),
    path(
        "maker/<str:tag_number>/place_history/",
        MakerViewSet.as_view({"get": "place_history"}),
        name="maker-place-history",
    ),
    path(
        "ram/<str:tag_number>/place_history/",
        RamViewSet.as_view({"get": "place_history"}),
        name="ram-place-history",
    ),
    path(
        "ewe/<str:tag_number>/place_history/",
        EweViewSet.as_view({"get": "place_history"}),
        name="ewe-place-history",
    ),
    path(
        "sheep/<str:tag_number>/place_history/",
        SheepViewSet.as_view({"get": "place_history"}),
        name="sheep-place-history",
    ),
    path(
        "maker/<str:tag_number>/restore/",
        MakerViewSet.as_view({"post": "restore"}),
        name="maker-restore",
    ),
    path(
        "ram/<str:tag_number>/restore/",
        RamViewSet.as_view({"post": "restore"}),
        name="ram-restore",
    ),
    path(
        "ewe/<str:tag_number>/restore/",
        EweViewSet.as_view({"post": "restore"}),
        name="ewe-restore",
    ),
    path(
        "sheep/<str:tag_number>/restore/",
        SheepViewSet.as_view({"post": "restore"}),
        name="sheep-restore",
    ),
    path("main/", animals, name="animals"),  # Главная страница
    path(
        "create/", create_animal, name="create_animal"
    ),  # Маршрут для создания животных
    path(
        "makers/", MakersView.as_view(), name="makers"
    ),  # Маршрут для страницы управления производителями
    path(
        "rams/", TemplateView.as_view(template_name="rams.html"), name="rams"
    ),  # Маршрут для страницы управления баранами
    path(
        "ewes/", TemplateView.as_view(template_name="ewes.html"), name="ewes"
    ),  # Маршрут для страницы управления ярками
    path(
        "sheeps/", TemplateView.as_view(template_name="sheeps.html"), name="sheeps"
    ),  # Маршрут для страницы управления овцами
]
