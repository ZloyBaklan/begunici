from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import Http404

from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase
from .serializers import MakerSerializer, MakerChildSerializer, RamSerializer, EweSerializer, SheepSerializer, LambingSerializer, ArchiveAnimalSerializer
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination

from begunici.app_types.veterinary.vet_models import WeightRecord, Veterinary, PlaceMovement, Tag, StatusHistory
from begunici.app_types.veterinary.vet_serializers import WeightRecordSerializer, VeterinarySerializer, PlaceMovementSerializer, StatusHistorySerializer

class PaginationSetting(PageNumberPagination):
    page_size = 10  # Количество записей на странице
    page_size_query_param = 'page_size'  # Возможность менять размер страницы
    max_page_size = 100  # Максимальное количество записей на странице
    
class AnimalBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter]
    pagination_class = PaginationSetting  # Добавляем пагинацию
    
    def handle_exception(self, exc):
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)



class MakerViewSet(viewsets.ModelViewSet):
    queryset = Maker.objects.filter(is_archived=False).order_by('id')  # Убедитесь, что порядок задан
    serializer_class = MakerSerializer
    filter_backends = [SearchFilter]
    search_fields = ['tag__tag_number', 'animal_status__status_type', 'place__sheepfold']
    pagination_class = PaginationSetting  # Добавляем пагинацию

    def get_object(self):
        print(f"DEBUG: self.kwargs содержат: {self.kwargs}")  # Логируем входные данные
        tag_number = self.kwargs['pk']
        print(f"Получен tag_number из URL: {tag_number}")  # Логируем значение
        """
        Переопределяем метод, чтобы искать объект по `tag_number`, а не по `pk`.
        """
        return Maker.objects.get(tag__tag_number=tag_number)

    @action(detail=True, methods=['post'], url_path='update_working_condition')
    def update_working_condition(self, request, pk=None):
        """
        Обновление рабочего состояния производителя с установкой даты.
        """
        try:
            maker = self.get_object()
            new_condition = request.data.get('working_condition')
            if not new_condition:
                return Response({'error': 'Не указано новое рабочее состояние.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Вызываем метод модели для обновления состояния
            maker.update_working_condition(new_condition)
            
            # Сериализуем и возвращаем обновлённый объект
            serializer = self.get_serializer(maker)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return self.handle_exception(e)


    @action(detail=True, methods=['post'], url_path='add_weight')
    def add_weight(self, request, pk=None):
        maker = self.get_object()
        weight_data = {
            'tag_number': maker.tag,
            'weight': request.data.get('weight'),
            'weight_date': request.data.get('date'),
        }
        serializer = WeightRecordSerializer(data=weight_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)



    @action(detail=True, methods=['post'], url_path='add_vet_care')
    def add_vet_care(self, request, pk=None):
        maker = self.get_object()
        vet_data = {
            'tag_number': maker,
            'care_type': request.data.get('care_type'),
            'care_name': request.data.get('care_name'),
            'medication': request.data.get('medication'),
            'purpose': request.data.get('purpose'),
            'date_of_care': request.data.get('date_of_care'),
        }
        serializer = VeterinarySerializer(data=vet_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'], url_path='weight_history')
    def weight_history(self, request, pk=None):
        maker = self.get_object()
        history = WeightRecord.objects.filter(tag__tag_number=maker.tag.tag_number).order_by('-weight_date')
        serializer = WeightRecordSerializer(history, many=True)
        return Response(serializer.data)


    @action(detail=True, methods=['get'], url_path='vet_history')
    def vet_history(self, request, pk=None):
        """
        Получаем историю ветобработок для животного.
        """

        maker = self.get_object()
        vet_history = Veterinary.objects.filter(tag__tag_number=maker.tag.tag_number).select_related('veterinary_care').order_by('-date_of_care')
        # Применяем пагинацию
        page = self.paginate_queryset(vet_history)
        if page is not None:
            serializer = VeterinarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Если пагинация не настроена, возвращаем все записи (лучше избегать этого)
        serializer = VeterinarySerializer(vet_history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'], url_path='place_history')
    def place_history(self, request, pk=None):
        """
        Возвращает историю перемещений для конкретного животного с поддержкой пагинации.
        """
        maker = self.get_object()  # Получаем объект Maker по tag_number
        place_movements = PlaceMovement.objects.filter(tag__tag_number=maker.tag.tag_number).order_by('-new_place__date_of_transfer')
        
        # Применяем пагинацию
        page = self.paginate_queryset(place_movements)
        if page is not None:
            serializer = PlaceMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Если пагинация не настроена, возвращаем все записи (лучше избегать этого)
        serializer = PlaceMovementSerializer(place_movements, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


    
    @action(detail=True, methods=['get'], url_path='status_history')
    def status_history(self, request, pk=None):
        """
        Возвращает историю статусов для конкретного животного с поддержкой пагинации.
        """
        maker = self.get_object()  # Получаем объект Maker
        status_history = StatusHistory.objects.filter(tag__tag_number=maker.tag.tag_number).order_by('-new_status__date_of_status')

        # Применяем пагинацию
        page = self.paginate_queryset(status_history)
        if page is not None:
            serializer = StatusHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Если пагинация не настроена, возвращаем все записи (не рекомендуется)
        serializer = StatusHistorySerializer(status_history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



    # Дети
    @action(detail=True, methods=['get'], url_path='children')
    def children(self, request, pk=None):
        maker = self.get_object()
        children = maker.get_children()
        # Применяем пагинацию
        page = self.paginate_queryset(children)
        if page is not None:
            serializer = MakerChildSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Если пагинация не настроена, возвращаем все записи (не рекомендуется)
        serializer = MakerChildSerializer(children, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='add_place_movement')
    def add_place_movement(self, request, pk=None):
        maker = self.get_object()
        movement_data = {
            'tag_number': maker.tag.tag_number,
            'old_place': request.data.get('old_place'),
            'new_place': request.data.get('new_place'),
            'date_of_transfer': request.data.get('new_place__date_of_transfer'),
        }
        serializer = PlaceMovementSerializer(data=movement_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

  
    @action(detail=True, methods=['get'], url_path='api')
    def retrieve_api(self, request, pk=None):
        maker = self.get_object()
        serializer = self.get_serializer(maker)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='family_tree')
    def family_tree(self, request, pk=None):
        """
        Получаем родителей и детей для животного.
        """
        maker = self.get_object()
        father = maker.father
        mother = maker.mother
        children = maker.get_children()  # Используем исправленный метод

        data = {
            'father': MakerSerializer(father).data if father else None,
            'mother': MakerSerializer(mother).data if mother else None,
            'children': MakerSerializer(children, many=True).data
        }
        return Response(data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['patch'], url_path='update_parents')
    def update_parents(self, request, pk=None):
        maker = self.get_object()

        mother_tag_number = request.data.get('mother_tag_number')
        father_tag_number = request.data.get('father_tag_number')

        # Обработка мамы
        if mother_tag_number:
            try:
                mother_tag = Tag.objects.get(tag_number=mother_tag_number)
                maker.mother = mother_tag
            except Tag.DoesNotExist:
                return Response({'error': f'Mother tag {mother_tag_number} not found'}, status=status.HTTP_400_BAD_REQUEST)
        elif mother_tag_number is None:
            maker.mother = None  # Если явно передан null, удаляем маму

        # Обработка папы
        if father_tag_number:
            try:
                father_tag = Tag.objects.get(tag_number=father_tag_number)
                maker.father = father_tag
            except Tag.DoesNotExist:
                return Response({'error': f'Father tag {father_tag_number} not found'}, status=status.HTTP_400_BAD_REQUEST)
        elif father_tag_number is None:
            maker.father = None  # Если явно передан null, удаляем папу

        maker.save()

        return Response({'success': 'Parents updated successfully'}, status=status.HTTP_200_OK)






class RamViewSet(AnimalBaseViewSet):
    queryset = Ram.objects.filter(is_archived=False)
    serializer_class = RamSerializer
    

class EweViewSet(AnimalBaseViewSet):
    queryset = Ewe.objects.filter(is_archived=False)
    serializer_class = EweSerializer
    

    @action(detail=True, methods=['post'])
    def to_sheep(self, request, pk=None, url_path='to_sheep'):
        try:
            ewe = self.get_object()
            sheep = ewe.to_sheep()
            return Response({'status': 'Ярка преобразована в овцу', 'new_sheep': SheepSerializer(sheep).data})
        except Exception as e:
            return self.handle_exception(e)

class SheepViewSet(AnimalBaseViewSet):
    queryset = Sheep.objects.filter(is_archived=False)
    serializer_class = SheepSerializer
    

    @action(detail=True, methods=['post'], url_path='add_lambing')
    def add_lambing(self, request, pk=None):
        sheep = self.get_object()
        maker = Maker.objects.get(tag_number=request.data.get('maker_id'))
        lambing = sheep.add_lambing(
            maker=maker,
            actual_lambing_date=request.data.get('actual_lambing_date'),
            lambs_data=request.data.get('lambs_data')
        )
        return Response(LambingSerializer(lambing).data)

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
        tag_number = self.kwargs.get('tag_number')
        maker = Maker.objects.filter(tag__tag_number=tag_number).first()
        try:
            maker = Maker.objects.get(tag__tag_number=tag_number)
            context['maker'] = maker
        except Maker.DoesNotExist:
            print(f"Maker with tag_number={tag_number} not found")  # Отладочная информация
            raise Http404("Производитель не найден")
        return context


class MakerAnalyticsView(TemplateView):
    template_name = 'maker_analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag_number = self.kwargs.get('tag_number')
        maker = Maker.objects.filter(tag__tag_number=tag_number).first()
        try:
            maker = Maker.objects.get(tag__tag_number=tag_number)
            context['maker'] = maker
        except Maker.DoesNotExist:
            raise Http404("Производитель не найден")
        # Используем метод сериализации детей
        serialized_maker = MakerSerializer(maker).data
        # Используем обновленный сериализатор для детей
        children = maker.get_children()  # Получаем детей через метод модели
        children_serialized = MakerChildSerializer(children, many=True).data
        context.update({
            'maker': serialized_maker,
            'children': children_serialized,  # Дети уже сериализованы
            'status_history': StatusHistorySerializer(
                StatusHistory.objects.filter(tag=maker.tag).order_by('-id'),
                many=True
            ).data,
            'place_movements': PlaceMovementSerializer(
                PlaceMovement.objects.filter(tag=maker.tag).order_by('-new_place__date_of_transfer'),
                many=True
            ).data,
            'veterinary_history': VeterinarySerializer(
                Veterinary.objects.filter(tag=maker.tag).order_by('-date_of_care'),
                many=True
            ).data,
            'weight_records': WeightRecordSerializer(
                WeightRecord.objects.filter(tag=maker.tag).order_by('-weight_date'),
                many=True
            ).data,
        })
        return context




class ArchiveViewSet(ListModelMixin, GenericViewSet):
    """
    ViewSet для общего архива животных.
    """
    serializer_class = ArchiveAnimalSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['tag__tag_number', 'animal_status__status_type', 'place__sheepfold']
    ordering_fields = ['birth_date', 'age', 'tag__tag_number']
    pagination_class = PaginationSetting  # Добавляем пагинацию

    def get_queryset(self):
        """
        Получаем архив всех животных, объединяя модели Maker, Sheep, Ewe и Ram.
        """
        animal_type = self.request.query_params.get('type', None)

        if animal_type == 'Maker':
            return Maker.objects.filter(is_archived=True)
        elif animal_type == 'Sheep':
            return Sheep.objects.filter(is_archived=True)
        elif animal_type == 'Ewe':
            return Ewe.objects.filter(is_archived=True)
        elif animal_type == 'Ram':
            return Ram.objects.filter(is_archived=True)

        # Объединение всех архивированных животных в один список
        makers = Maker.objects.filter(is_archived=True).values(
            'id', 'tag__tag_number', 'tag__animal_type', 'animal_status__status_type', 'animal_status__date_of_status',  'place__sheepfold', 'birth_date', 'age'
        )
        sheep = Sheep.objects.filter(is_archived=True).values(
            'id', 'tag__tag_number', 'tag__animal_type', 'animal_status__status_type', 'animal_status__date_of_status',  'place__sheepfold', 'birth_date', 'age'
        )
        ewes = Ewe.objects.filter(is_archived=True).values(
            'id', 'tag__tag_number', 'tag__animal_type', 'animal_status__status_type', 'animal_status__date_of_status',  'place__sheepfold', 'birth_date', 'age'
        )
        rams = Ram.objects.filter(is_archived=True).values(
            'id', 'tag__tag_number', 'tag__animal_type', 'animal_status__status_type', 'animal_status__date_of_status',  'place__sheepfold', 'birth_date', 'age'
        )

        return makers.union(sheep, ewes, rams)




# Представления для страниц

def animals(request):
    return render(request, 'animals.html')

def create_animal(request):
    return render(request, 'create_animal.html')


