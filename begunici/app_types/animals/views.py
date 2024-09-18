from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.shortcuts import render
from django.views.generic import TemplateView

from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase
from .serializers import MakerSerializer, RamSerializer, EweSerializer, SheepSerializer, LambingSerializer, AnimalSerializer
from django_filters.rest_framework import DjangoFilterBackend

class MakerViewSet(viewsets.ModelViewSet):
    queryset = Maker.objects.all()
    serializer_class = MakerSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tag', 'animal_status']

    @action(detail=True, methods=['post'])
    def update_working_condition(self, request, pk=None):
        maker = self.get_object()
        new_condition = request.data.get('working_condition')
        maker.update_working_condition(new_condition)
        return Response({'status': 'Рабочее состояние обновлено'}, status=status.HTTP_200_OK)

class RamViewSet(viewsets.ModelViewSet):
    queryset = Ram.objects.all()
    serializer_class = RamSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tag', 'animal_status', 'mother_tag', 'father_tag']

class EweViewSet(viewsets.ModelViewSet):
    queryset = Ewe.objects.all()
    serializer_class = EweSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tag', 'animal_status', 'mother_tag', 'father_tag']

    @action(detail=True, methods=['post'])
    def to_sheep(self, request, pk=None):
        ewe = self.get_object()
        sheep = ewe.to_sheep()  # Преобразование ярки в овцу
        return Response({'status': 'Ярка преобразована в овцу', 'new_sheep': SheepSerializer(sheep).data})

class SheepViewSet(viewsets.ModelViewSet):
    queryset = Sheep.objects.all()
    serializer_class = SheepSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tag', 'animal_status', 'mother_tag', 'father_tag']

    @action(detail=True, methods=['post'])
    def add_lambing(self, request, pk=None):
        sheep = self.get_object()
        maker_id = request.data.get('maker_id')
        actual_lambing_date = request.data.get('actual_lambing_date')
        lambs_data = request.data.get('lambs_data')

        lambing = sheep.add_lambing(maker_id, actual_lambing_date, lambs_data)
        return Response({'status': 'Окот добавлен', 'lambing': LambingSerializer(lambing).data})

class LambingViewSet(viewsets.ModelViewSet):
    queryset = Lambing.objects.all()
    serializer_class = LambingSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['ewe', 'maker', 'actual_lambing_date', 'planned_lambing_date']

class AnimalViewSet(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def archive(self, request):
        # Фильтруем архивные животные по статусу "Убыл", "Убой", "Продажа"
        archived_statuses = ['Убыл', 'Убой', 'Продажа']
        sheep_queryset = Sheep.objects.filter(animal_status__status_type__in=archived_statuses)
        ram_queryset = Ram.objects.filter(animal_status__status_type__in=archived_statuses)
        ewe_queryset = Ewe.objects.filter(animal_status__status_type__in=archived_statuses)
        maker_queryset = Maker.objects.filter(animal_status__status_type__in=archived_statuses)

        # Сериализуем данные
        sheep_data = SheepSerializer(sheep_queryset, many=True).data
        ram_data = RamSerializer(ram_queryset, many=True).data
        ewe_data = EweSerializer(ewe_queryset, many=True).data
        maker_data = MakerSerializer(maker_queryset, many=True).data

        # Возвращаем данные всех архивных животных
        return Response({
            'sheep': sheep_data,
            'rams': ram_data,
            'ewes': ewe_data,
            'makers': maker_data
        })

# Представление для главной страницы
def animals(request):
    return render(request, 'animals.html')

def create_animal(request):
    return render(request, 'create_animal.html')

# Классовое представление для рендеринга страницы управления уходом
class MakersView(TemplateView):
    template_name = 'makers.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Можно добавить контекст для шаблона, если нужно
        return context