from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Veterinary, Status, Tag, VeterinaryCare, WeightRecord, Place
from .serializers import (
    StatusSerializer, TagSerializer, VeterinarySerializer, VeterinaryCareSerializer
    , WeightRecordSerializer, WeightChangeSerializer, PlaceSerializer
)

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

class VeterinaryViewSet(viewsets.ModelViewSet):
    queryset = Veterinary.objects.all()
    serializer_class = VeterinarySerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['veterinary_care__care_type', 'date_of_care', 'tag']  # Фильтрация по типу обработки, дате и бирке

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации


class WeightRecordViewSet(viewsets.ModelViewSet):
    queryset = WeightRecord.objects.all()
    serializer_class = WeightRecordSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации

    @action(detail=True, methods=['get'])
    def weight_history(self, request, pk=None):
        """
        Получаем всю историю веса животного по бирке.
        """
        tag = self.get_object().tag
        history = WeightRecord.get_weight_history(tag)
        serializer = WeightRecordSerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def weight_changes(self, request, pk=None):
        """
        Получаем изменения веса для животного.
        """
        tag = self.get_object().tag
        changes = WeightRecord.get_weight_changes(tag)
        serializer = WeightChangeSerializer(changes, many=True)
        return Response(serializer.data)