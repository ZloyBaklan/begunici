from rest_framework import viewsets, status, filters
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.shortcuts import render
from django.views.generic import TemplateView
from rest_framework.exceptions import ValidationError
from .vet_models import (
    Veterinary,
    Status,
    Tag,
    VeterinaryCare,
    WeightRecord,
    Place,
    PlaceMovement,
)
from .vet_serializers import (
    StatusSerializer,
    TagSerializer,
    VeterinarySerializer,
    VeterinaryCareSerializer,
    WeightRecordSerializer,
    PlaceSerializer,
    PlaceMovementSerializer,
)
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


def places_map(request):
    """
    Представление для карты овчарен
    """
    return render(request, "places_map.html")


@api_view(['GET'])
def get_animals_by_place(request, place_id):
    """
    Возвращает список животных в указанном месте
    """
    try:
        from begunici.app_types.animals.models import Maker, Ram, Ewe, Sheep
        
        animals = []
        
        # Получаем животных всех типов в данном месте
        makers = Maker.objects.filter(place_id=place_id, is_archived=False).select_related('tag', 'animal_status')
        rams = Ram.objects.filter(place_id=place_id, is_archived=False).select_related('tag', 'animal_status')
        ewes = Ewe.objects.filter(place_id=place_id, is_archived=False).select_related('tag', 'animal_status')
        sheep = Sheep.objects.filter(place_id=place_id, is_archived=False).select_related('tag', 'animal_status')
        
        # Формируем список животных
        for maker in makers:
            animals.append({
                'type': 'Производитель',
                'tag_number': maker.tag.tag_number if maker.tag else 'Нет бирки',
                'status': maker.animal_status.status_type if maker.animal_status else 'Нет статуса',
                'age': maker.age
            })
            
        for ram in rams:
            animals.append({
                'type': 'Баран',
                'tag_number': ram.tag.tag_number if ram.tag else 'Нет бирки',
                'status': ram.animal_status.status_type if ram.animal_status else 'Нет статуса',
                'age': ram.age
            })
            
        for ewe in ewes:
            animals.append({
                'type': 'Ярка',
                'tag_number': ewe.tag.tag_number if ewe.tag else 'Нет бирки',
                'status': ewe.animal_status.status_type if ewe.animal_status else 'Нет статуса',
                'age': ewe.age
            })
            
        for s in sheep:
            animals.append({
                'type': 'Овца',
                'tag_number': s.tag.tag_number if s.tag else 'Нет бирки',
                'status': s.animal_status.status_type if s.animal_status else 'Нет статуса',
                'age': s.age
            })
        
        return Response(animals)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class PlaceMovementPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 100


class StatusViewSet(viewsets.ModelViewSet):
    queryset = Status.objects.all().order_by("-date_of_status")
    serializer_class = StatusSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["date_of_status"]
    search_fields = ["status_type"]


class PlaceViewSet(viewsets.ModelViewSet):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["sheepfold"]


class PlaceMovementViewSet(viewsets.ModelViewSet):
    queryset = PlaceMovement.objects.select_related("new_place", "old_place").order_by(
        "-new_place__date_of_transfer"
    )
    serializer_class = PlaceMovementSerializer
    permission_classes = [AllowAny]
    pagination_class = PlaceMovementPagination


class VeterinaryCareViewSet(viewsets.ModelViewSet):
    queryset = VeterinaryCare.objects.all()
    serializer_class = VeterinaryCareSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["care_type", "care_name", "medication", "purpose"]


class VeterinaryViewSet(viewsets.ModelViewSet):
    queryset = Veterinary.objects.all()
    serializer_class = VeterinarySerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "veterinary_care__care_type",
        "date_of_care",
        "tag__tag_number",
    ]
    search_fields = [
        "tag__tag_number",
        "veterinary_care__care_type",
        "veterinary_care__care_name",
        "veterinary_care__medication",
        "veterinary_care__purpose",
        "comments",
    ]


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination


class WeightRecordViewSet(viewsets.ModelViewSet):
    queryset = WeightRecord.objects.all().order_by("-weight_date")
    serializer_class = WeightRecordSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination


class VeterinaryManagementView(TemplateView):
    template_name = "veterinary_management.html"


class VeterinaryStatusesView(TemplateView):
    template_name = "veterinary_statuses.html"


class VeterinaryPlacesView(TemplateView):
    template_name = "veterinary_places.html"


class VeterinaryCaresView(TemplateView):
    template_name = "veterinary_cares.html"
