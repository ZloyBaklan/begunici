from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect


class PublicModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.APP_MODE == 'public':
            if settings.DEBUG:
                return HttpResponse('Public deployment requires DEBUG=False', status=503)
            if request.path_info == '/':
                return HttpResponseRedirect('/site/')
            if not request.path_info.startswith(('/site/', '/static/')):
                return HttpResponse(status=404)
        return self.get_response(request)


class LoginRequiredExceptPublicMiddleware:
    """
    Разрешаем без логина только явно перечисленные пути.
    Всё остальное требует аутентификацию.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        self.public_prefixes = (
            "/site/",  # публичный сайт
            "/login/",  # внутренний логин
            "/login",  # внутренний логин без слеша
            "/accounts/login/",  # legacy URL логина
            "/accounts/logout/",  # legacy URL логаута
            "/admin/login/",  # логин админки
            "/static/",  # статика
            "/api/scales/v1/",  # закрытый Basic Auth API весового терминала
        )

    def __call__(self, request):
        path = request.path

        # Разрешённые пути доступны без авторизации
        if path.startswith(self.public_prefixes):
            return self.get_response(request)

        # Админка работает по своим правилам
        if path.startswith("/admin/"):
            return self.get_response(request)

        # Всё остальное требует логин
        if not request.user.is_authenticated:
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"/login/?{query}")

        return self.get_response(request)
