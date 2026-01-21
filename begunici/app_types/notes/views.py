from datetime import date as date_type

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.dateparse import parse_date

from rest_framework import permissions, generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Note
from .serializers import NoteSerializer


@login_required
def notes_page(request):
    return render(request, "notes/notes.html")


class NoteListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NoteSerializer

    def get_queryset(self):
        qs = Note.objects.filter(user=self.request.user)

        d_from = parse_date(self.request.query_params.get("from", "") or "")
        d_to = parse_date(self.request.query_params.get("to", "") or "")

        if d_from:
            qs = qs.filter(date__gte=d_from)
        if d_to:
            qs = qs.filter(date__lte=d_to)

        return qs.order_by("date", "created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class NotesByDayView(APIView):
    """
    GET /notes/api/day/YYYY-MM-DD/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, day: str):
        d = parse_date(day)
        if not d:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD"}, status=400)

        notes = Note.objects.filter(user=request.user, date=d).order_by("created_at")
        return Response(NoteSerializer(notes, many=True).data)

