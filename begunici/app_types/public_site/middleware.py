'''

from django.shortcuts import redirect
from django.urls import reverse

class AppLoginRequiredMiddleware:
    """
    Всё, что начинается с /app/ — только для залогиненных.
    Исключения: /app/login/, /admin/ и статика обычно не сюда.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if path.startswith("/app/"):
            if not request.user.is_authenticated:
                # куда редиректить — зависит auth url'ов
                login_url = reverse("login")  # если подключены django.contrib.auth.urls
                return redirect(f"{login_url}?next={path}")

        return self.get_response(request)
'''

from django.shortcuts import redirect
from django.urls import reverse

class LoginRequiredExceptPublicMiddleware:
    """
    Разрешаем без логина только явно перечисленные пути.
    Всё остальное — требует аутентификацию.
    """
    def __init__(self, get_response):
        self.get_response = get_response

        self.public_prefixes = (
            "/site/",            # публичный сайт
            "/accounts/login/",  # логин
            "/accounts/logout/", # логаут (можно и убрать)
            "/admin/login/",     # если нужен логин в админку
            "/static/",          # статика в дев-режиме
        )

        # Если у тебя media:
        # self.public_prefixes += ("/media/",)

    def __call__(self, request):
        path = request.path

        # Разрешённые пути — всегда ок
        if path.startswith(self.public_prefixes):
            return self.get_response(request)

        # Админку можно либо закрыть как "внутреннюю" (тогда убрать /admin/login/ из public),
        # либо оставить как есть. Обычно админку тоже закрывают, но ей нужен login.
        if path.startswith("/admin/"):
            # Пусть админ работает по своим правилам
            return self.get_response(request)

        # Всё остальное требует логин
        if not request.user.is_authenticated:
            login_url = reverse("login")  # /accounts/login/
            return redirect(f"{login_url}?next={path}")

        return self.get_response(request)
