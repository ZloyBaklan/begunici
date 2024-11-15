from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import render
from django.views.generic import TemplateView
from rest_framework.exceptions import ValidationError
from .models import Veterinary, Status, Tag, VeterinaryCare, WeightRecord, Place
from .serializers import (
    StatusSerializer, TagSerializer, VeterinarySerializer, VeterinaryCareSerializer
    , WeightRecordSerializer, WeightChangeSerializer, PlaceSerializer
)

class StatusViewSet(viewsets.ModelViewSet):
    queryset = Status.objects.all()
    serializer_class = StatusSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации
    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

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


# Представление для отображения страницы управления технической информацией
class VeterinaryManagementView(TemplateView):
    template_name = 'veterinary_management.html'  # Указываем шаблон

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Можно добавить контекст для шаблона, если нужно
        return context

# Классовое представление для рендеринга страницы управления статусами
class VeterinaryStatusesView(TemplateView):
    template_name = 'veterinary_statuses.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Можно добавить контекст для шаблона, если нужно
        return context

# Классовое представление для рендеринга страницы управления овчарнями
class VeterinaryPlacesView(TemplateView):
    template_name = 'veterinary_places.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Можно добавить контекст для шаблона, если нужно
        return context

# Классовое представление для рендеринга страницы управления уходом
class VeterinaryCaresView(TemplateView):
    template_name = 'veterinary_cares.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Можно добавить контекст для шаблона, если нужно
        return context