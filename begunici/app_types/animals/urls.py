from django.urls import path
from begunici.app_types.animals import views as a_views

urlpatterns = [    
    
    # Создание новых объектов
    path('create/maker/', a_views.create_maker, name='create_maker'),
    path('create/ram/', a_views.create_ram, name='create_ram'),
    path('create/ewe/', a_views.create_ewe, name='create_ewe'),
    path('create/sheep/', a_views.create_sheep, name='create_sheep'),
    path('create/lamb/', a_views.create_lamb, name='create_lamb'),
    path('create/lambing/', a_views.create_lambing, name='create_lambing'),
    

    # Вывод списков объектов
    path('list/makers/', a_views.maker_list, name='maker_list'),
    path('list/rams/', a_views.ram_list, name='ram_list'),
    path('list/ewes/', a_views.ewe_list, name='ewe_list'),
    path('list/sheep/', a_views.sheep_list, name='sheep_list'),
    path('list/lambs/', a_views.lamb_list, name='lamb_list'),
    path('list/lambing/', a_views.list_lambing, name='list_lambing'),

    # Преобразование Ewe в Sheep
    path('ewe-to-sheep/<int:ewe_id>/', a_views.ewe_to_sheep, name='ewe_to_sheep'),

    # Перенос Lamb в Ram или Ewe
    path('lamb-to-ram-or-ewe/<int:lamb_id>/', a_views.lamb_to_ram_or_ewe, name='lamb_to_ram_or_ewe'),

    # Фильтрация по различным параметрам
    path('filter/<str:model_name>/', a_views.animal_filter, name='animal_filter'),
    
    # Фильтрация овец по производителю (папа)
    path('sheep-by-maker/<int:maker_id>/', a_views.sheep_by_maker, name='sheep_by_maker'),

    ]
