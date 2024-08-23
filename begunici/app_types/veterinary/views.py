from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import render
from begunici.app_types.animals.models import Sheep, Lambing
from begunici.app_types.animals.serializers import LambingSerializer
from .models import Veterinary, Status, Tag, VeterinaryCare, WeightRecord, Place
from .serializers import (
    StatusSerializer, TagSerializer, VeterinaryCareSerializer,
    WeightRecordSerializer, PlaceSerializer
)
@method_decorator(csrf_exempt, name='dispatch')
class StatusViewSet(viewsets.ModelViewSet):
    queryset = Status.objects.all()
    serializer_class = StatusSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации

class PlaceViewSet(viewsets.ModelViewSet):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации

class VeterinaryCareViewSet(viewsets.ModelViewSet):
    queryset = VeterinaryCare.objects.all()
    serializer_class = VeterinaryCareSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации


# Представление для отображения формы создания объектов
def create_veterinary(request):
    return render(request, 'veterinary/create_objects.html')

def sheep_lambings(request):
    return render(request, 'veterinary/create_objects.html')