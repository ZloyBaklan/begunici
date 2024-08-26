from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StatusViewSet, PlaceViewSet, VeterinaryCareViewSet, 
    VeterinaryViewSet, TagViewSet, WeightRecordViewSet
)

# Создаем роутер
router = DefaultRouter()

# Регистрируем ViewSet'ы
router.register(r'status', StatusViewSet)
router.register(r'place', PlaceViewSet)
router.register(r'veterinary-care', VeterinaryCareViewSet)
router.register(r'veterinary', VeterinaryViewSet)
router.register(r'tag', TagViewSet)
router.register(r'weight-record', WeightRecordViewSet)

urlpatterns = [
    path('', include(router.urls)),  # Добавляем имя для veterinary
    # Маршруты, которые не связаны с ViewSet (например, получение всех окотов для овцы)
]
