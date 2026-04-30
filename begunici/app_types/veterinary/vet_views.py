from rest_framework import viewsets, status, filters
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic import TemplateView
from rest_framework.exceptions import ValidationError
from datetime import datetime
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
            display_name = maker.tag.tag_number if maker.tag else 'Нет бирки'
            if maker.name and maker.tag:
                display_name = f"{maker.name}({maker.tag.tag_number})"
            
            animals.append({
                'type': 'Производитель',
                'tag_number': maker.tag.tag_number if maker.tag else 'Нет бирки',
                'display_name': display_name,
                'status': maker.animal_status.status_type if maker.animal_status else 'Нет статуса',
                'age': maker.age
            })
            
        for ram in rams:
            animals.append({
                'type': 'Баран',
                'tag_number': ram.tag.tag_number if ram.tag else 'Нет бирки',
                'display_name': ram.tag.tag_number if ram.tag else 'Нет бирки',
                'status': ram.animal_status.status_type if ram.animal_status else 'Нет статуса',
                'age': ram.age
            })
            
        for ewe in ewes:
            animals.append({
                'type': 'Ярка',
                'tag_number': ewe.tag.tag_number if ewe.tag else 'Нет бирки',
                'display_name': ewe.tag.tag_number if ewe.tag else 'Нет бирки',
                'status': ewe.animal_status.status_type if ewe.animal_status else 'Нет статуса',
                'age': ewe.age
            })
            
        for s in sheep:
            animals.append({
                'type': 'Овца',
                'tag_number': s.tag.tag_number if s.tag else 'Нет бирки',
                'display_name': s.tag.tag_number if s.tag else 'Нет бирки',
                'status': s.animal_status.status_type if s.animal_status else 'Нет статуса',
                'age': s.age
            })
        
        return Response(animals)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_barn_statistics(request, barn_number):
    """
    Возвращает статистику по конкретной овчарне
    """
    try:
        from begunici.app_types.animals.models import Maker, Ram, Ewe, Sheep
        from django.db.models import Count, Q
        
        # Получаем места для этой овчарни
        places = Place.objects.filter(sheepfold__icontains=f'Овчарня {barn_number} Отсек')
        place_ids = list(places.values_list('id', flat=True))
        
        if not place_ids:
            return Response({
                'barn_number': barn_number,
                'sections': [],
                'total_animals': 0,
                'animals_by_section': {}
            })
        
        # Получаем статистику по отсекам
        sections_data = []
        animals_by_section = {}
        total_animals = 0
        
        for place in places:
            # Извлекаем номер отсека
            import re
            match = re.search(r'Отсек (\d+)', place.sheepfold)
            if not match:
                continue
                
            section_number = int(match.group(1))
            
            # Считаем животных в этом отсеке
            makers_count = Maker.objects.filter(place=place, is_archived=False).count()
            rams_count = Ram.objects.filter(place=place, is_archived=False).count()
            ewes_count = Ewe.objects.filter(place=place, is_archived=False).count()
            sheep_count = Sheep.objects.filter(place=place, is_archived=False).count()
            
            section_total = makers_count + rams_count + ewes_count + sheep_count
            total_animals += section_total
            
            sections_data.append({
                'id': place.id,
                'name': place.sheepfold,
                'section_number': section_number,
                'animals_count': section_total
            })
            
            animals_by_section[place.id] = {
                'makers': makers_count,
                'rams': rams_count,
                'ewes': ewes_count,
                'sheep': sheep_count,
                'total': section_total
            }
        
        # Сортируем отсеки по номерам
        sections_data.sort(key=lambda x: x['section_number'])
        
        return Response({
            'barn_number': barn_number,
            'sections': sections_data,
            'total_animals': total_animals,
            'animals_by_section': animals_by_section
        })
        
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
    queryset = Status.objects.all().order_by("-id")  # Сортировка по ID (новые вначале)
    serializer_class = StatusSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["status_type"]


class PlaceViewSet(viewsets.ModelViewSet):
    queryset = Place.objects.all().order_by("-id")  # Сортировка по ID (новые вначале)
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
    queryset = VeterinaryCare.objects.all().order_by("-id")  # Сортировка по ID (новые вначале)
    serializer_class = VeterinaryCareSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
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


# Специальные endpoints без пагинации для select элементов
@api_view(['GET'])
def get_all_statuses(request):
    """
    Возвращает все статусы без пагинации для select элементов
    """
    statuses = Status.objects.all().order_by('status_type')
    serializer = StatusSerializer(statuses, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def get_all_places(request):
    """
    Возвращает все места без пагинации для select элементов
    """
    places = Place.objects.all().order_by('sheepfold')
    serializer = PlaceSerializer(places, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def get_all_veterinary_cares(request):
    """
    Возвращает все ветобработки без пагинации для select элементов
    """
    cares = VeterinaryCare.objects.all().order_by('care_type', 'care_name')
    serializer = VeterinaryCareSerializer(cares, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def export_veterinary_cares_excel(request):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return Response(
            {"error": "Библиотека openpyxl не установлена. Экспорт XLSX недоступен."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    cares = VeterinaryCare.objects.all().order_by("id")

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Vet Cares"

    headers = [
        "№",
        "ID",
        "Тип ветобработки",
        "Класс ветобработки",
        "Препарат/материал",
        "Цель",
        "Срок действия (дней)",
    ]

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    for col_num, header in enumerate(headers, 1):
        cell = worksheet.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for index, care in enumerate(cares, start=1):
        row = [
            index,
            care.id,
            care.care_type,
            care.care_name,
            care.medication or "",
            care.purpose or "",
            care.default_duration_days,
        ]
        worksheet.append(row)

    for column_cells in worksheet.columns:
        max_length = 0
        column_index = column_cells[0].column
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            if len(value) > max_length:
                max_length = len(value)
        worksheet.column_dimensions[get_column_letter(column_index)].width = min(max_length + 2, 60)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f'veterinary_cares_{datetime.now().strftime("%Y-%m-%d")}.xlsx'
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    workbook.save(response)
    return response
