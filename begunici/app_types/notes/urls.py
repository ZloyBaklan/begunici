from django.urls import path

from . import views

app_name = "notes"

urlpatterns = [
    path("", views.notes_page, name="notes"),
    path("api/notes/", views.NoteListCreateView.as_view(), name="api-notes"),
    path("api/day/<str:day>/", views.NotesByDayView.as_view(), name="api-notes-day"),
]
