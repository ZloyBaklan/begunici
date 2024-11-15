from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.shortcuts import render
from django.views.generic import TemplateView

from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase
from .serializers import MakerSerializer, RamSerializer, EweSerializer, SheepSerializer, LambingSerializer
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination

class PaginationSetting(PageNumberPagination):
    page_size = 20  # Количество записей на странице
    page_size_query_param = 'page_size'  # Возможность менять размер страницы
    max_page_size = 100  # Максимальное количество записей на странице
    
class AnimalBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter]
    
    
    def handle_exception(self, exc):
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

class MakerViewSet(AnimalBaseViewSet):
    queryset = Maker.objects.all()
    serializer_class = MakerSerializer
    pagination_class = PaginationSetting  # Добавляем пагинацию
    search_fields = ['tag__tag_number', 'animal_status__status_type', 'place__sheepfold']


    @action(detail=True, methods=['post'])
    def update_working_condition(self, request, pk=None):
        try:
            maker = self.get_object()
            new_condition = request.data.get('working_condition')
            maker.update_working_condition(new_condition)
            return Response({'status': 'Рабочее состояние обновлено'}, status=status.HTTP_200_OK)
        except Exception as e:
            return self.handle_exception(e)
    

class RamViewSet(AnimalBaseViewSet):
    queryset = Ram.objects.all()
    serializer_class = RamSerializer
    

class EweViewSet(AnimalBaseViewSet):
    queryset = Ewe.objects.all()
    serializer_class = EweSerializer
    

    @action(detail=True, methods=['post'])
    def to_sheep(self, request, pk=None):
        try:
            ewe = self.get_object()
            sheep = ewe.to_sheep()
            return Response({'status': 'Ярка преобразована в овцу', 'new_sheep': SheepSerializer(sheep).data})
        except Exception as e:
            return self.handle_exception(e)

class SheepViewSet(AnimalBaseViewSet):
    queryset = Sheep.objects.all()
    serializer_class = SheepSerializer
    

    @action(detail=True, methods=['post'])
    def add_lambing(self, request, pk=None):
        try:
            sheep = self.get_object()
            maker_id = request.data.get('maker_id')
            actual_lambing_date = request.data.get('actual_lambing_date')
            lambs_data = request.data.get('lambs_data')

            maker = Maker.objects.get(id=maker_id)
            lambing = sheep.add_lambing(maker, actual_lambing_date, lambs_data)
            return Response({'status': 'Окот добавлен', 'lambing': LambingSerializer(lambing).data}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return self.handle_exception(e)

class LambingViewSet(viewsets.ModelViewSet):
    queryset = Lambing.objects.all()
    serializer_class = LambingSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter]

class MakersView(TemplateView):
    template_name = 'makers.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class MakerDetailView(TemplateView):
    template_name = 'maker_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

# Представления для страниц

def animals(request):
    return render(request, 'animals.html')

def create_animal(request):
    return render(request, 'create_animal.html')
