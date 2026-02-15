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
from django.contrib.auth import views as auth_views
from .views import index  # Импортируем view для главной страницы
from begunici.app_types.veterinary.vet_views import places_map  # Импортируем view для карты овчарен
from begunici.app_types.animals.views_admin import admin_panel, admin_logs_api  # Импортируем admin views

urlpatterns = [
    path("admin/", admin.site.urls),  # Панель администратора Django
    path("", index, name="index"),  # Главная страница
    path("places/map/", places_map, name="places_map"),  # Карта овчарен
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),  # Выход
    path("accounts/login/", auth_views.LoginView.as_view(template_name='admin/login.html'), name="login"),  # Логин
    # Панель администратора для логов
    path("admin-panel/", admin_panel, name="admin_panel"),  # Панель администратора
    path("admin-panel/logs/api/", admin_logs_api, name="admin_logs_api"),  # API для логов
    path(
        "site/",
        include(("begunici.app_types.public_site.urls", "public_site"), namespace="public_site"),
    ),  # Публичный сайт
    path(
        "veterinary/",
        include(
            ("begunici.app_types.veterinary.vet_urls", "veterinary"),
            namespace="veterinary",
        ),
    ),  # Подключаем urls для veterinary с namespace
    path(
        "animals/",
        include(("begunici.app_types.animals.urls", "animals"), namespace="animals"),
    ),  # Подключаем urls для animals с namespace
]
