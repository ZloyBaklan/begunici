from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny

from .models import Maker, Ram, Ewe, Sheep, Lambing
from .serializers import MakerSerializer, RamSerializer, EweSerializer, SheepSerializer, LambingSerializer
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
