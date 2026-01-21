from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from begunici.app_types.animals.models import Maker


# Представление для главной страницы
@login_required
def index(request):
    return render(request, "index.html")


# Представление для списка Makers
@login_required
def maker_list(request):
    makers = Maker.objects.all()
    return render(request, "animals/list_makers.html", {"makers": makers})
