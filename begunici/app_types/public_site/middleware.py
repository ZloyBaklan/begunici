from urllib.parse import urlencode

from django.shortcuts import redirect


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
