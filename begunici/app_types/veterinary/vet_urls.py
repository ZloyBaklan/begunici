from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .vet_views import (
    StatusViewSet, PlaceViewSet, VeterinaryCareViewSet, PlaceMovementViewSet,
    VeterinaryViewSet, TagViewSet, WeightRecordViewSet, VeterinaryManagementView, VeterinaryStatusesView, VeterinaryPlacesView, VeterinaryCaresView
)

# Создаем роутер
router = DefaultRouter()

# Регистрируем ViewSet'ы
router.register(r'status', StatusViewSet)
router.register(r'place', PlaceViewSet)
router.register(r'care', VeterinaryCareViewSet)
router.register(r'veterinary', VeterinaryViewSet)
router.register(r'tag', TagViewSet)
router.register(r'weight-record', WeightRecordViewSet)
#router.register(r'place_movement', PlaceMovementViewSet)

urlpatterns = [
    path('', include(router.urls)),  # Добавляем имя для veterinary
    path('management/', VeterinaryManagementView.as_view(), name='veterinary-management'),  # Страница управления технической информацией
    path('statuses/', VeterinaryStatusesView.as_view(), name='veterinary_statuses'),  # Маршрут для страницы управления статусами
    path('places/', VeterinaryPlacesView.as_view(), name='veterinary_places'),  # Маршрут для страницы управления местами
    path('cares/', VeterinaryCaresView.as_view(), name='veterinary_cares'),  # Маршрут для страницы управления типами ухода
    
]
