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
from django.urls import path, include  # Для подключения маршрутов приложений
import begunici.views

urlpatterns = [
    path('', begunici.views.index, name='index'),  # Главная страница приложения animals
    path('admin/', admin.site.urls),
    path('create/', begunici.views.create_veterinary, name='create_veterinary'),  # Путь для создания
    path('animals/', include('begunici.app_types.animals.urls')),  # Подключаем маршруты animals
    path('veterinary/', include('begunici.app_types.veterinary.urls')),  # Подключаем маршруты veterinary
]
