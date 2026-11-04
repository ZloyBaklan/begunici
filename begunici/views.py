from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from begunici.app_types.animals.models import Maker


# Представление для главной страницы
@login_required
def index(request):
    return render(request, "index.html")


def internal_login(request):
    params = request.POST if request.method == "POST" else request.GET
    next_url = params.get("next", "/")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        next_url = "/"
    if request.user.is_authenticated:
        return redirect(next_url)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None and user.username != "scales":
                login(request, user)
                return redirect(next_url)
            messages.error(request, "Неверное имя пользователя или пароль.")
        else:
            messages.error(request, "Введите логин и пароль.")

    return render(request, "internal_login.html", {
        "next": next_url, "demo_password": settings.DEMO_LOGIN_PASSWORD,
    })


# Представление для списка Makers
@login_required
def maker_list(request):
    makers = Maker.objects.all()
    return render(request, "animals/list_makers.html", {"makers": makers})
