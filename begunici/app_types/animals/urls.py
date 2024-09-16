from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MakerViewSet, RamViewSet, EweViewSet, SheepViewSet, LambingViewSet, AnimalViewSet, animals, create_animal
)

# Создаем маршруты для ViewSet
router = DefaultRouter()
router.register(r'maker', MakerViewSet)         # Маршрут для производителей
router.register(r'ram', RamViewSet)             # Маршрут для баранов
router.register(r'ewe', EweViewSet)             # Маршрут для ярок
router.register(r'sheep', SheepViewSet)         # Маршрут для овец
router.register(r'lambing', LambingViewSet)     # Маршрут для окотов
router.register(r'archive', AnimalViewSet, basename='archive')     # Маршрут для архива

# Подключаем router для управления всеми ViewSet
urlpatterns = [
    path('', include(router.urls)),
    path('main/', animals, name='animals'),  # Главная страница
    path('create/', create_animal, name='create_animal'),  # Маршрут для создания животных

]


