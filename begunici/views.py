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
    if request.user.is_authenticated:
        return redirect("/")

    next_url = request.GET.get("next", "/")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                post_next = request.POST.get("next", "/")

                if post_next and url_has_allowed_host_and_scheme(
                    post_next, allowed_hosts={request.get_host()}
                ):
                    return redirect(post_next)

                return redirect("/")

            messages.error(request, "Неверное имя пользователя или пароль.")
        else:
            messages.error(request, "Введите логин и пароль.")

    return render(request, "internal_login.html", {"next": next_url})


# Представление для списка Makers
@login_required
def maker_list(request):
    makers = Maker.objects.all()
    return render(request, "animals/list_makers.html", {"makers": makers})
