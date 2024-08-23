"""
URL configuration for begunici project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from begunici.app_types.veterinary.views import StatusViewSet, PlaceViewSet, VeterinaryCareViewSet
from .views import index  # Импортируем view для главной страницы
# from begunici.app_types.animals.views import MakerViewSet, RamViewSet, EweViewSet, SheepViewSet, LambViewSet

# Создаем один общий роутер для всех ViewSet
router = DefaultRouter()
# Маршруты для veterinary
router.register(r'status', StatusViewSet)
router.register(r'place', PlaceViewSet)
router.register(r'veterinary-care', VeterinaryCareViewSet)

# Маршруты для animals
#router.register(r'maker', MakerViewSet)
#router.register(r'ram', RamViewSet)
#router.register(r'ewe', EweViewSet)
#router.register(r'sheep', SheepViewSet)
#router.register(r'lamb', LambViewSet)

urlpatterns = [
    path('api/', include(router.urls)),  # Все API маршруты для ViewSet
    path('veterinary/', include('begunici.app_types.veterinary.urls')),  # Включаем URL из veterinary
    #path('animals/', include('begunici.app_types.animals.urls')),  # Включаем URL из animals
    path('admin/', admin.site.urls),  # Панель администратора
    path('', index, name='index'),  # Главная страница
]

