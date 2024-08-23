from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

from .views import MakerViewSet


router = DefaultRouter()
router.register(r'maker', MakerViewSet)

urlpatterns = [
    path('', include(router.urls)),
    # Любые кастомные маршруты, которые не обрабатываются ViewSet
    path('ewe-to-sheep/<int:ewe_id>/', views.ewe_to_sheep, name='ewe_to_sheep'),
    path('lamb-to-ram-or-ewe/<int:lamb_id>/', views.lamb_to_ram_or_ewe, name='lamb_to_ram_or_ewe'),
    path('filter/<str:model_name>/', views.animal_filter, name='animal_filter'),
    path('sheep-by-maker/<int:maker_id>/', views.sheep_by_maker, name='sheep_by_maker'),
]

