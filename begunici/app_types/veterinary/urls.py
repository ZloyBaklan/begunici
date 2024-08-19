from django.urls import path
from begunici.app_types.veterinary import views as vet_views

urlpatterns = [

    # Создание новых объектов
    path('create/veterinary/', vet_views.create_veterinary, name='create_veterinary'),
    path('place/create/', vet_views.create_status, name='create_status'),
    path('create/tag/', vet_views.create_tag, name='create_tag'),
    path('veterinary-care/create/', vet_views.create_veterinary_care, name='create_veterinary_care'),
    path('create/weight-record/', vet_views.create_weight_record, name='create_weight_record'),
    # Вывод списков объектов
    path('list/veterinary/', vet_views.list_veterinary, name='list_veterinary'),
    path('list/statuses/', vet_views.list_statuses, name='list_statuses'),
    path('list/tags/', vet_views.list_tags, name='list_tags'),
    path('list/veterinary-care/', vet_views.list_veterinary_care, name='list_veterinary_care'),
    path('list/weight-records/', vet_views.list_weight_records, name='list_weight_records'),

    path('list/places/', vet_views.list_places, name='list_places'),

    # Вывод всех окотов (Lambing) для конкретной овцы
    path('sheep/<int:sheep_id>/lambings/', vet_views.sheep_lambings, name='sheep_lambings'),
]