from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action
from datetime import datetime
from django.shortcuts import render
from django.views.generic import TemplateView
from rest_framework.exceptions import ValidationError
from .vet_models import Veterinary, Status, Tag, VeterinaryCare, WeightRecord, Place, PlaceMovement
from .vet_serializers import (
    StatusSerializer, TagSerializer, VeterinarySerializer, VeterinaryCareSerializer
    , WeightRecordSerializer, WeightChangeSerializer, PlaceSerializer, PlaceMovementSerializer
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

class PlaceMovementViewSet(viewsets.ModelViewSet):
    queryset = PlaceMovement.objects.all().order_by('-transfer_date')
    serializer_class = PlaceMovementSerializer
    permission_classes = [AllowAny]



class VeterinaryCareViewSet(viewsets.ModelViewSet):
    queryset = VeterinaryCare.objects.all()
    serializer_class = VeterinaryCareSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации

    @action(detail=False, methods=['get'], url_path='all_cares')
    def get_cares(self, request):
        """
        Возвращает список всех существующих ветобработок.
        """
        cares = self.queryset
        serializer = self.get_serializer(cares, many=True)
        return Response(serializer.data)

class VeterinaryViewSet(viewsets.ModelViewSet):
    queryset = Veterinary.objects.all()
    serializer_class = VeterinarySerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['veterinary_care__care_type', 'date_of_care', 'tag']  # Фильтрация по типу обработки, дате и бирке

    @action(detail=False, methods=['post'], url_path='vetcare')
    def add_vet_care(self, request):
        """
        Добавление ветобработки животному.
        """
        tag_id = request.data.get('tag')
        treatment_id = request.data.get('treatment_id')
        date_of_care = request.data.get('date_of_care')

        if not tag_id or not treatment_id or not date_of_care:
            return Response({'error': 'Все поля обязательны'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Получаем объекты
            tag = Tag.objects.get(id=tag_id)
            veterinary_care = VeterinaryCare.objects.get(id=treatment_id)

            # Создаем новую запись
            Veterinary.objects.create(
                tag=tag,
                veterinary_care=veterinary_care,
                date_of_care=date_of_care,
                comments=request.data.get('comments', '')
            )

            return Response({'status': 'Ветобработка успешно добавлена'}, status=status.HTTP_201_CREATED)
        except (Tag.DoesNotExist, VeterinaryCare.DoesNotExist):
            return Response({'error': 'Бирка или обработка не найдены'}, status=status.HTTP_404_NOT_FOUND)



class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации

    @action(detail=False, methods=['get'], url_path='search')
    def search_tag(self, request):
        """
        Поиск бирки по номеру.
        """
        tag_number = request.query_params.get('tag_number', None)
        if not tag_number:
            return Response({'error': 'tag_number is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            tag = Tag.objects.get(tag_number=tag_number)
            serializer = self.get_serializer(tag)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Tag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)


class WeightRecordViewSet(viewsets.ModelViewSet):
    queryset = WeightRecord.objects.all().order_by('-weight_date')  # Сортировка по дате
    serializer_class = WeightRecordSerializer
    permission_classes = [AllowAny]  # Доступ без аутентификации

    @action(detail=False, methods=['get'])
    def weight_history(self, request):
        """
        Получаем всю историю веса по бирке, переданной через query parameter.
        """
        tag_id = request.query_params.get('tag')
        if not tag_id:
            return Response({'error': 'Tag ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        history = WeightRecord.get_weight_history(tag_id)
        serializer = WeightRecordSerializer(history, many=True)
        return Response(serializer.data)


    @action(detail=False, methods=['get'])
    def weight_changes(self, request):
        """
        Получаем изменения веса для животного.
        """
        tag_id = request.query_params.get('tag')
        if not tag_id:
            return Response({'error': 'Tag ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        changes = WeightRecord.get_weight_changes(tag_id)
        return Response(changes)

    @action(detail=False, methods=['post'])
    def add_weight(self, request):
        """
        Добавление новой записи веса.
        """
        tag_id = request.data.get('tag')
        weight = request.data.get('weight')
        weight_date = request.data.get('weight_date')

        if not tag_id or not weight or not weight_date:
            return Response({'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Проверка и преобразование даты
            weight_date = datetime.strptime(weight_date, '%Y-%m-%d').date()
            tag = Tag.objects.get(id=tag_id)
            WeightRecord.objects.create(tag=tag, weight=weight, weight_date=weight_date)
            return Response({'status': 'Weight record added successfully'}, status=status.HTTP_201_CREATED)
        except Tag.DoesNotExist:
            return Response({'error': 'Tag not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



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