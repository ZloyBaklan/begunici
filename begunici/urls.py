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
from django.urls import path
from begunici.animals import views as a_views
from begunici.veterinary import views as vet_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Создание новых объектов
    path('create/veterinary/', vet_views.create_veterinary, name='create_veterinary'),
    path('create/status/', vet_views.create_status, name='create_status'),
    path('create/tag/', vet_views.create_tag, name='create_tag'),
    path('create/veterinary-care/', vet_views.create_veterinary_care, name='create_veterinary_care'),
    path('create/weight-record/', vet_views.create_weight_record, name='create_weight_record'),
    path('create/lambing/', vet_views.create_lambing, name='create_lambing'),
    path('create/place/', vet_views.create_place, name='create_place'),

    # Вывод списков объектов
    path('list/veterinary/', vet_views.list_veterinary, name='list_veterinary'),
    path('list/statuses/', vet_views.list_statuses, name='list_statuses'),
    path('list/tags/', vet_views.list_tags, name='list_tags'),
    path('list/veterinary-care/', vet_views.list_veterinary_care, name='list_veterinary_care'),
    path('list/weight-records/', vet_views.list_weight_records, name='list_weight_records'),
    path('list/lambing/', vet_views.list_lambing, name='list_lambing'),
    path('list/places/', vet_views.list_places, name='list_places'),

    # Вывод всех окотов (Lambing) для конкретной овцы
    path('sheep/<int:sheep_id>/lambings/', vet_views.sheep_lambings, name='sheep_lambings'),

    # Создание новых объектов
    path('create/maker/', a_views.create_maker, name='create_maker'),
    path('create/ram/', a_views.create_ram, name='create_ram'),
    path('create/ewe/', a_views.create_ewe, name='create_ewe'),
    path('create/sheep/', a_views.create_sheep, name='create_sheep'),
    path('create/lamb/', a_views.create_lamb, name='create_lamb'),

    # Вывод списков объектов
    path('list/makers/', a_views.maker_list, name='maker_list'),
    path('list/rams/', a_views.ram_list, name='ram_list'),
    path('list/ewes/', a_views.ewe_list, name='ewe_list'),
    path('list/sheep/', a_views.sheep_list, name='sheep_list'),
    path('list/lambs/', a_views.lamb_list, name='lamb_list'),

    # Преобразование Ewe в Sheep
    path('ewe-to-sheep/<int:ewe_id>/', a_views.ewe_to_sheep, name='ewe_to_sheep'),

    # Перенос Lamb в Ram или Ewe
    path('lamb-to-ram-or-ewe/<int:lamb_id>/', a_views.lamb_to_ram_or_ewe, name='lamb_to_ram_or_ewe'),

    # Фильтрация по различным параметрам
    path('filter/<str:model_name>/', a_views.animal_filter, name='animal_filter'),
    
    # Фильтрация овец по производителю (папа)
    path('sheep-by-maker/<int:maker_id>/', a_views.sheep_by_maker, name='sheep_by_maker'),



]
