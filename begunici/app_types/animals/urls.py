from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MakerViewSet, RamViewSet, EweViewSet, SheepViewSet, LambingViewSet
)

# Создаем маршруты для ViewSet
router = DefaultRouter()
router.register(r'maker', MakerViewSet)         # Маршрут для производителей
router.register(r'ram', RamViewSet)             # Маршрут для баранов
router.register(r'ewe', EweViewSet)             # Маршрут для ярок
router.register(r'sheep', SheepViewSet)         # Маршрут для овец
router.register(r'lambing', LambingViewSet)     # Маршрут для окотов

# Подключаем router для управления всеми ViewSet
urlpatterns = [
    path('', include(router.urls)),
]


