from django.urls import path
from . import views

urlpatterns = [
    # Маршруты, которые не связаны с ViewSet (например, получение всех окотов для овцы)
    path('sheep/<int:sheep_id>/lambings/', views.sheep_lambings, name='sheep_lambings'),
]
