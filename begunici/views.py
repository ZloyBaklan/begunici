from django.shortcuts import render
from begunici.app_types.animals.models import Maker


# Представление для главной страницы
def index(request):
    return render(request, 'index.html')



# Представление для списка Makers
def maker_list(request):
    makers = Maker.objects.all()
    return render(request, 'animals/list_makers.html', {'makers': makers})
