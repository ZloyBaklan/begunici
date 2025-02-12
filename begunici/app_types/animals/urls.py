from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from .views import (
    MakerViewSet, MakersView, MakerDetailView, MakerAnalyticsView, RamViewSet, EweViewSet, SheepViewSet, LambingViewSet, animals, create_animal, ArchiveViewSet
)

# Создаем маршруты для ViewSet
router = DefaultRouter()
router.register(r'maker', MakerViewSet)         # Маршрут для производителей
router.register(r'ram', RamViewSet)             # Маршрут для баранов
router.register(r'ewe', EweViewSet)             # Маршрут для ярок
router.register(r'sheep', SheepViewSet)         # Маршрут для овец
router.register(r'lambing', LambingViewSet)     # Маршрут для окотов
router.register(r'archive', ArchiveViewSet, basename='archive')  # Архив животных

# Подключаем router для управления всеми ViewSet
urlpatterns = [
    path('maker/<int:pk>/info/', MakerDetailView.as_view(), name='maker-detail'),
    path('makers/<int:pk>/analytics/', MakerAnalyticsView.as_view(), name='maker-analytics'),
    path('main_archive/', TemplateView.as_view(template_name='archive.html'), name='main_archive'),
    path('', include(router.urls)),
    path('maker/<int:pk>/api/', MakerViewSet.as_view({'get': 'retrieve_api'}), name='maker-api'),
    path('maker/<int:pk>/update_parents/', MakerViewSet.as_view({'patch': 'update_parents'}), name='update-parents'),
    #path('maker/<int:pk>/weight_history/', MakerViewSet.as_view({'get': 'weight_history'}), name='weight-history'),
    #path('maker/<int:pk>/add_weight/', MakerViewSet.as_view({'post': 'add_weight'}), name='add-weight'),
    #path('maker/<int:pk>/vet_history/', MakerViewSet.as_view({'get': 'vet_history'}), name='vet-history'),
    #path('maker/<int:pk>/place_history/', MakerViewSet.as_view({'get': 'place_history'}), name='place-history'),
    #path('maker/place_movement/', MakerViewSet.as_view({'post': 'add_place_movement'}), name='add-place-movement'),
    path('maker/<int:pk>/children/', MakerViewSet.as_view({'get': 'children'}), name='maker-children'),
    path('maker/<int:pk>/status_history/', MakerViewSet.as_view({'get': 'status_history'}), name='maker-status-history'),
    path('maker/<int:pk>/place_history/', MakerViewSet.as_view({'get': 'place_history'}), name='maker-place-history'),
    path('main/', animals, name='animals'),  # Главная страница
    path('create/', create_animal, name='create_animal'),  # Маршрут для создания животных
    path('makers/', MakersView.as_view(), name='makers'),  # Маршрут для страницы управления типами ухода
    ]


