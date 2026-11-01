from django.urls import path
from . import views

app_name = "clinical"
urlpatterns = [
    path("", views.journal, name="journal"),
    path("care/", views.care, name="care"),
    path("command/<str:action>/", views.command, name="command"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/command/<str:action>/", views.command, name="episode-command"),
]
