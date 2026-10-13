import re

from django.contrib.auth.decorators import login_required
from django.db import transaction
from rest_framework import viewsets, status, filters
from rest_framework.permissions import AllowAny, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from django.utils import timezone
from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic import TemplateView
from rest_framework.exceptions import ValidationError
from django.db.models import Q
from datetime import date, datetime, timedelta
from calendar import monthrange
from .vet_models import (
    Veterinary,
    Status,
    Tag,
    VeterinaryCare,
    WeightRecord,
    Place,
    PlaceMovement,
    BarnCalculatorProfile,
)
from .barn_calculator import (
    CalculatorInputError, DEFAULT_PARAMETERS, GROUPS, PARAMETER_LABELS,
    build_factual_composition, calculate_barn, empty_composition,
    normalize_barn_number, normalize_composition, normalize_parameters, parameters_to_json,
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
from begunici.app_types.animals.models import ARCHIVE_STATUS_NAMES
from begunici.app_types.animals.age_utils import age_months_for_export
from begunici.app_types.animals.status_logic import get_allowed_active_status_names_for_animal_type
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status


def place_natural_sort_key(place):
    numbers = [int(value) for value in re.findall(r"\d+", place.sheepfold or "")]
    barn_number = numbers[0] if len(numbers) >= 1 else 10**9
    section_number = numbers[1] if len(numbers) >= 2 else 10**9
    return (barn_number, section_number, (place.sheepfold or "").lower())


def _build_text_case_variants_filter(field_name, value):
    combined_q = Q()
    for term in [part.strip() for part in str(value or "").split(",") if part.strip()]:
        variants = {term, term.lower(), term.upper(), term.title()}
        for variant in variants:
            combined_q |= Q(**{f"{field_name}__contains": variant})
    return combined_q


def places_map(request):
    """
    Представление для карты овчарен
    """
    return render(request, "places_map.html")


@api_view(["GET"])
def export_feed_plan_excel(request):
    try:
        # FEED BRIDGE: прежний URL скачивания использует общие нормы и итоги.
        from begunici.app_types.feed_inventory.plan import feed_plan_response

        return feed_plan_response()
    except FileNotFoundError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except RuntimeError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


PLACE_MAP_EXCEL_DATE_FORMAT = "dd.mm.yyyy"


def _coerce_place_map_excel_date(value):
    if not value or value == "-":
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return None


def _write_place_map_excel_cell(worksheet, row_index, column_index, value):
    parsed_date = _coerce_place_map_excel_date(value)
    cell = worksheet.cell(
        row=row_index,
        column=column_index,
        value=parsed_date or value,
    )
    if parsed_date:
        cell.number_format = PLACE_MAP_EXCEL_DATE_FORMAT
    return cell


def _format_place_map_dorper_display(animal):
    if animal.dorper_percentage is None:
        return None

    percentage = float(animal.dorper_percentage)
    formatted = f"{int(percentage)}%" if percentage == int(percentage) else f"{percentage:g}%"
    if getattr(animal, "is_manual_dorper", False):
        formatted += "*"
    return formatted


def _parse_place_map_export_place_ids(raw_place_ids):
    if isinstance(raw_place_ids, str):
        raw_place_ids = [value.strip() for value in raw_place_ids.split(",")]
    elif raw_place_ids is None:
        raw_place_ids = []
    elif not isinstance(raw_place_ids, (list, tuple, set)):
        raw_place_ids = [raw_place_ids]

    place_ids = []
    seen_ids = set()
    for raw_place_id in raw_place_ids:
        try:
            place_id = int(raw_place_id)
        except (TypeError, ValueError):
            continue

        if place_id not in seen_ids:
            place_ids.append(place_id)
            seen_ids.add(place_id)

    return place_ids


@api_view(["POST"])
def export_place_map_excel(request):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        from begunici.app_types.animals.models import Ewe, Maker, Ram, Sheep
    except ImportError:
        return Response(
            {"error": "Библиотека openpyxl не установлена. Экспорт Excel недоступен."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    place_ids = _parse_place_map_export_place_ids(request.data.get("place_ids"))
    if not place_ids:
        return Response(
            {"error": "Выберите хотя бы один отсек для экспорта."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    animal_type_map = {
        "maker": (Maker, "Баран-Производитель"),
        "ram": (Ram, "Баранчик"),
        "ewe": (Ewe, "Ярка"),
        "sheep": (Sheep, "Овцематка"),
    }

    raw_animal_types = request.data.get("animal_types")
    if raw_animal_types is None:
        raw_animal_types = request.data.get("animal_type", "all")
    if isinstance(raw_animal_types, str):
        raw_animal_types = [value.strip() for value in raw_animal_types.split(",")]
    elif not isinstance(raw_animal_types, (list, tuple, set)):
        raw_animal_types = [raw_animal_types]

    selected_animal_type_keys = []
    invalid_animal_types = []
    for raw_animal_type in raw_animal_types:
        animal_type_key = str(raw_animal_type or "").strip().lower()
        if not animal_type_key:
            continue
        if animal_type_key == "all":
            selected_animal_type_keys = list(animal_type_map.keys())
            invalid_animal_types = []
            break
        if animal_type_key not in animal_type_map:
            invalid_animal_types.append(animal_type_key)
            continue
        if animal_type_key not in selected_animal_type_keys:
            selected_animal_type_keys.append(animal_type_key)

    if invalid_animal_types:
        return Response(
            {"error": "Выбран неизвестный тип животных для экспорта."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not selected_animal_type_keys:
        return Response(
            {"error": "Выберите хотя бы один тип животных для экспорта."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    places = list(Place.objects.filter(id__in=place_ids))
    if not places:
        return Response(
            {"error": "Выбранные отсеки не найдены."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    places = sorted(places, key=place_natural_sort_key)
    place_order = {place.id: index for index, place in enumerate(places)}
    selected_models = [
        (animal_type_key, animal_type_map[animal_type_key])
        for animal_type_key in selected_animal_type_keys
    ]

    animal_entries = []
    selected_place_ids = list(place_order.keys())
    for type_order, (_, (model, type_label)) in enumerate(selected_models):
        queryset = (
            model.objects
            .filter(is_archived=False, place_id__in=selected_place_ids)
            .select_related("tag", "animal_status", "place")
        )
        for animal in queryset:
            animal_entries.append({
                "animal": animal,
                "type_label": type_label,
                "type_order": type_order,
            })

    animal_entries.sort(key=lambda entry: (
        place_order.get(entry["animal"].place_id, 10**9),
        entry["type_order"],
        (entry["animal"].tag.tag_number if entry["animal"].tag else "").lower(),
    ))

    tag_ids = [
        entry["animal"].tag_id
        for entry in animal_entries
        if getattr(entry["animal"], "tag_id", None)
    ]
    latest_weights_by_tag = {}
    if tag_ids:
        for weight_record in (
            WeightRecord.objects
            .filter(tag_id__in=tag_ids)
            .order_by("tag_id", "-weight_date", "-id")
        ):
            latest_weights_by_tag.setdefault(weight_record.tag_id, weight_record)

    headers = [
        "№",
        "Тип животного",
        "Бирка",
        "Статус",
        "Возраст (мес)",
        "Овчарня",
        "Кровность по основной породе",
        "Назначение",
        "Живой вес (кг)",
        "Дата взвешивания",
        "Рабочее состояние",
        "Примечание",
    ]

    export_rows = []
    for row_number, entry in enumerate(animal_entries, start=1):
        animal = entry["animal"]
        latest_weight = latest_weights_by_tag.get(animal.tag_id)
        export_rows.append([
            row_number,
            entry["type_label"],
            animal.tag.tag_number if animal.tag else "-",
            animal.animal_status.status_type if animal.animal_status else "Нет статуса",
            age_months_for_export(animal.birth_date),
            animal.place.sheepfold if animal.place else "Нет данных",
            _format_place_map_dorper_display(animal) or "-",
            animal.get_assignment_display(),
            float(latest_weight.weight) if latest_weight else "-",
            latest_weight.weight_date if latest_weight else "-",
            animal.working_condition if hasattr(animal, "working_condition") and animal.working_condition else "-",
            animal.note or "",
        ])

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Карта овчарен"

    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    for column_index, header in enumerate(headers, start=1):
        cell = worksheet.cell(row=1, column=column_index, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_index, row_data in enumerate(export_rows, start=2):
        for column_index, value in enumerate(row_data, start=1):
            cell = _write_place_map_excel_cell(worksheet, row_index, column_index, value)
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    column_widths = [8, 24, 16, 18, 14, 24, 24, 14, 16, 18, 22, 36]
    for column_index, width in enumerate(column_widths, start=1):
        worksheet.column_dimensions[get_column_letter(column_index)].width = width

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    filename = f"place_map_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    workbook.save(response)
    return response


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
                'type': 'Баран-Производитель',
                'tag_number': maker.tag.tag_number if maker.tag else 'Нет бирки',
                'rshn_tag': maker.rshn_tag or '',
                'display_name': display_name,
                'status': maker.animal_status.status_type if maker.animal_status else 'Нет статуса',
                'age': maker.get_age_months()
            })
            
        for ram in rams:
            animals.append({
                'type': 'Баранчик',
                'tag_number': ram.tag.tag_number if ram.tag else 'Нет бирки',
                'rshn_tag': ram.rshn_tag or '',
                'display_name': ram.tag.tag_number if ram.tag else 'Нет бирки',
                'status': ram.animal_status.status_type if ram.animal_status else 'Нет статуса',
                'age': ram.get_age_months()
            })
            
        for ewe in ewes:
            animals.append({
                'type': 'Ярка',
                'tag_number': ewe.tag.tag_number if ewe.tag else 'Нет бирки',
                'rshn_tag': ewe.rshn_tag or '',
                'display_name': ewe.tag.tag_number if ewe.tag else 'Нет бирки',
                'status': ewe.animal_status.status_type if ewe.animal_status else 'Нет статуса',
                'age': ewe.get_age_months()
            })
            
        for s in sheep:
            animals.append({
                'type': 'Овцематка',
                'tag_number': s.tag.tag_number if s.tag else 'Нет бирки',
                'rshn_tag': s.rshn_tag or '',
                'display_name': s.tag.tag_number if s.tag else 'Нет бирки',
                'status': s.animal_status.status_type if s.animal_status else 'Нет статуса',
                'age': s.get_age_months()
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
        
        today = timezone.localdate()
        current_month_start = today.replace(day=1)
        current_month_end = today.replace(
            day=monthrange(today.year, today.month)[1]
        )
        previous_month_end = current_month_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)

        def _avg(values):
            if not values:
                return None
            return round(sum(values) / len(values), 1)

        def _get_age_months_as_of(animal, as_of_date):
            return animal.get_age_months(as_of_date)

        def _build_period_stats(
            animal_entries,
            as_of_date,
            period_start=None,
            period_end=None,
        ):
            eligible_entries = []
            for entry in animal_entries:
                animal = entry["animal"]
                if animal.birth_date and animal.birth_date > as_of_date:
                    continue
                eligible_entries.append(entry)

            counts = {
                "makers": 0,
                "rams": 0,
                "ewes": 0,
                "sheep": 0,
            }
            age_values = []
            lamb_tag_ids = set()
            all_tag_ids = []
            lamb_cutoff_date = as_of_date - timedelta(days=100)

            for entry in eligible_entries:
                type_key = entry["type"]
                animal = entry["animal"]

                if type_key in counts:
                    counts[type_key] += 1

                if getattr(animal, "tag_id", None):
                    all_tag_ids.append(animal.tag_id)

                age_months = _get_age_months_as_of(animal, as_of_date)
                if age_months is not None:
                    age_values.append(age_months)

                if (
                    animal.birth_date
                    and not animal.date_otbivka
                    and lamb_cutoff_date < animal.birth_date <= as_of_date
                    and getattr(animal, "tag_id", None)
                ):
                    lamb_tag_ids.add(animal.tag_id)

            total = counts["makers"] + counts["rams"] + counts["ewes"] + counts["sheep"]

            avg_weight_kg = None
            avg_weight_lambs_kg = None
            avg_weight_others_kg = None

            if all_tag_ids:
                weights_qs = (
                    WeightRecord.objects
                    .filter(tag_id__in=all_tag_ids)
                )
                if period_start and period_end:
                    weights_qs = weights_qs.filter(
                        weight_date__gte=period_start,
                        weight_date__lte=period_end,
                    )

                latest_weights = (
                    weights_qs
                    .order_by("tag_id", "-weight_date", "-id")
                    .distinct("tag_id")
                )

                weight_by_tag = {
                    record.tag_id: float(record.weight)
                    for record in latest_weights
                    if record.weight is not None
                }
                all_weights = list(weight_by_tag.values())
                lamb_weights = [
                    weight_by_tag[tag_id]
                    for tag_id in lamb_tag_ids
                    if tag_id in weight_by_tag
                ]
                other_weights = [
                    value
                    for tag_id, value in weight_by_tag.items()
                    if tag_id not in lamb_tag_ids
                ]

                avg_weight_kg = _avg(all_weights)
                avg_weight_lambs_kg = _avg(lamb_weights)
                avg_weight_others_kg = _avg(other_weights)

            return {
                "makers": counts["makers"],
                "rams": counts["rams"],
                "ewes": counts["ewes"],
                "sheep": counts["sheep"],
                "total": total,
                "lambs_count": len(lamb_tag_ids),
                "avg_age_months": _avg(age_values),
                "avg_weight_kg": avg_weight_kg,
                "avg_weight_lambs_kg": avg_weight_lambs_kg,
                "avg_weight_others_kg": avg_weight_others_kg,
                "period_start": (
                    period_start.strftime("%d.%m.%Y")
                    if period_start
                    else None
                ),
                "period_end": (
                    period_end.strftime("%d.%m.%Y")
                    if period_end
                    else None
                ),
            }
        
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
            
            # Получаем животных в этом отсеке
            makers = list(Maker.objects.filter(place=place, is_archived=False).select_related('tag'))
            rams = list(Ram.objects.filter(place=place, is_archived=False).select_related('tag'))
            ewes = list(Ewe.objects.filter(place=place, is_archived=False).select_related('tag'))
            sheep = list(Sheep.objects.filter(place=place, is_archived=False).select_related('tag'))

            makers_count = len(makers)
            rams_count = len(rams)
            ewes_count = len(ewes)
            sheep_count = len(sheep)
            animal_entries = (
                [{"type": "makers", "animal": item} for item in makers]
                + [{"type": "rams", "animal": item} for item in rams]
                + [{"type": "ewes", "animal": item} for item in ewes]
                + [{"type": "sheep", "animal": item} for item in sheep]
            )
            
            section_total = makers_count + rams_count + ewes_count + sheep_count
            total_animals += section_total

            snapshot_stats = _build_period_stats(
                animal_entries=animal_entries,
                as_of_date=today,
            )
            current_month_stats = _build_period_stats(
                animal_entries=animal_entries,
                as_of_date=current_month_end,
                period_start=current_month_start,
                period_end=current_month_end,
            )
            previous_month_stats = _build_period_stats(
                animal_entries=animal_entries,
                as_of_date=previous_month_end,
                period_start=previous_month_start,
                period_end=previous_month_end,
            )
            
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
                'total': section_total,
                'avg_age_months': snapshot_stats['avg_age_months'],
                'avg_weight_kg': snapshot_stats['avg_weight_kg'],
                'avg_weight_lambs_kg': snapshot_stats['avg_weight_lambs_kg'],
                'avg_weight_others_kg': snapshot_stats['avg_weight_others_kg'],
                'lambs_count': snapshot_stats['lambs_count'],
                'current_month': current_month_stats,
                'previous_month': previous_month_stats,
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

    archive_statuses = ARCHIVE_STATUS_NAMES
    non_select_statuses = {"Брак"}

    def get_queryset(self):
        queryset = super().get_queryset()
        exclude_archive = str(self.request.query_params.get("exclude_archive", "")).lower()
        exclude_non_select = str(self.request.query_params.get("exclude_non_select", "")).lower()
        animal_type = self.request.query_params.get("animal_type")
        if exclude_archive in {"1", "true", "yes"} or exclude_non_select in {"1", "true", "yes"}:
            queryset = queryset.exclude(status_type__in=self.non_select_statuses)
        if exclude_archive in {"1", "true", "yes"}:
            queryset = queryset.exclude(status_type__in=self.archive_statuses)
        if animal_type:
            allowed_statuses = get_allowed_active_status_names_for_animal_type(animal_type)
            if allowed_statuses is None:
                return queryset.none()
            queryset = queryset.filter(status_type__in=allowed_statuses)
        return queryset


class PlaceViewSet(viewsets.ModelViewSet):
    queryset = Place.objects.all().order_by("-id")  # Сортировка по ID (новые вначале)
    serializer_class = PlaceSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(_build_text_case_variants_filter("sheepfold", search))
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        sorted_places = sorted(queryset, key=place_natural_sort_key)

        page = self.paginate_queryset(sorted_places)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(sorted_places, many=True)
        return Response(serializer.data)


class PlaceMovementViewSet(viewsets.ModelViewSet):
    queryset = PlaceMovement.objects.select_related("new_place", "old_place").order_by(
        "-created_at"
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
    places = sorted(Place.objects.all(), key=place_natural_sort_key)
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
        "Класс ветобработки",
        "Тип ветобработки",
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



@login_required
def barn_calculator_page(request):
    return render(request, "barn_calculator.html")


def _barn_calculator_profile_data(number, profile=None):
    return {
        "barn_number": number, "has_saved_parameters": profile is not None,
        "parameters": parameters_to_json(normalize_parameters(profile.parameters if profile else {})),
        "manual_composition": normalize_composition(profile.manual_composition if profile else {}),
        "updated_at": profile.updated_at.isoformat() if profile else None,
    }


def _barn_calculator_payload(request):
    if not isinstance(request.data, dict):
        raise CalculatorInputError("Данные расчёта должны быть объектом")
    return request.data


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def barn_calculator_config(request):
    profiles = {profile.barn_number: profile for profile in BarnCalculatorProfile.objects.all()}
    return Response({
        "profiles": [_barn_calculator_profile_data(number, profiles.get(number)) for number in range(1, 5)],
        "defaults": DEFAULT_PARAMETERS, "empty_composition": empty_composition(),
        "norms": [
            {"key": key, "label": label, "base_area": area, "base_front": front, "section_limit": limit}
            for key, label, area, front, limit in GROUPS
        ],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def barn_calculator_factual(request):
    try:
        return Response(build_factual_composition(request.query_params.get("barn_number")))
    except CalculatorInputError as exc:
        return Response({"error": str(exc)}, status=400)


def _barn_calculator_result(data):
    barn_number = normalize_barn_number(data.get("barn_number"), allow_arbitrary=True)
    mode = data.get("composition_mode", "manual")
    if not isinstance(mode, str) or mode not in {"manual", "factual"}:
        raise CalculatorInputError("Выберите ручную или фактическую компоновку")
    factual = None
    if mode == "factual":
        if barn_number is None:
            raise CalculatorInputError("Фактическая компоновка доступна только для овчарен 1–4")
        factual = build_factual_composition(barn_number)
    parameters = normalize_parameters(data.get("parameters", {}))
    composition = factual["composition"] if factual else data.get("composition", {})
    result = calculate_barn(parameters, composition)
    result.update({
        "composition_mode": mode, "barn_number": barn_number,
        "factual": factual, "as_of_date": timezone.localdate().isoformat(),
        "complete": not factual or not factual["warnings"],
        "parameters": parameters_to_json(parameters),
    })
    # Incomplete factual data must never be presented as a full compliance pass.
    if not result["complete"] and result["passed"]:
        result["passed"] = None
    return result


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def barn_calculator_calculate(request):
    try:
        return Response(_barn_calculator_result(_barn_calculator_payload(request)))
    except CalculatorInputError as exc:
        return Response({"error": str(exc)}, status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def barn_calculator_save(request):
    try:
        data = _barn_calculator_payload(request)
        number = normalize_barn_number(data.get("barn_number"))
        if "parameters" not in data or "manual_composition" not in data:
            raise CalculatorInputError("Для сохранения передайте параметры и ручную компоновку")
        parameters = parameters_to_json(normalize_parameters(data["parameters"]))
        manual = normalize_composition(data["manual_composition"])
    except CalculatorInputError as exc:
        return Response({"error": str(exc)}, status=400)
    with transaction.atomic():
        profile, created = BarnCalculatorProfile.objects.select_for_update().get_or_create(barn_number=number)
        old_parameters = parameters_to_json(normalize_parameters(profile.parameters))
        old_manual = normalize_composition(profile.manual_composition)
        changed_labels = [PARAMETER_LABELS[key] for key in parameters if parameters[key] != old_parameters[key]]
        if manual != old_manual:
            changed_labels.append("Ручная компоновка")
        if created or changed_labels:
            profile.parameters = parameters
            profile.manual_composition = manual
            profile.save(update_fields=["parameters", "manual_composition", "updated_at"])
            from begunici.app_types.animals.models_user_log import UserActionLog
            UserActionLog.objects.create(
                user=request.user, action_type="Сохранение параметров овчарни",
                object_type="Калькулятор овчарни", object_id=str(number),
                description=f"Овчарня {number}: " + ("параметры сохранены впервые" if created else "изменены " + ", ".join(changed_labels)),
                additional_data={"parameters": parameters, "manual_composition": manual},
            )
    return Response(_barn_calculator_profile_data(number, profile))


def _barn_calculator_fill_sheet(xml, values, *, styles=None, row_heights=None, formulas=None):
    from xml.etree import ElementTree as ET

    styles, row_heights, formulas = styles or {}, row_heights or {}, formulas or {}
    cells_by_row = {}
    for address, value in values.items():
        number = int(re.search(r"\d+$", address).group())
        cells_by_row.setdefault(number, {})[address] = value

    def column_number(address):
        number = 0
        for letter in re.match(r"[A-Z]+", address).group():
            number = number * 26 + ord(letter) - ord("A") + 1
        return number

    def fill_cell(address, value, original=None):
        cell = ET.fromstring(original) if original else ET.Element("c", r=address)
        if address in styles:
            cell.set("s", str(styles[address]))
        for child in list(cell):
            if child.tag in {"v", "is"}:
                cell.remove(child)
        formula = cell.find("f")
        if address in formulas:
            if formula is None:
                formula = ET.SubElement(cell, "f")
            formula.text = formulas[address]
        if isinstance(value, str):
            value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
            cell.set("t", "str" if formula is not None else "inlineStr")
            if formula is not None:
                ET.SubElement(cell, "v").text = value
            else:
                text = ET.SubElement(ET.SubElement(cell, "is"), "t")
                text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                text.text = value
        else:
            cell.attrib.pop("t", None)
            ET.SubElement(cell, "v").text = str(value)
        return ET.tostring(cell, encoding="unicode")

    def fill_rows(match):
        rows = {}
        for row in re.finditer(r'<row\b([^>]*)>(.*?)</row>', match[1], re.S):
            attrs, body = row.groups()
            number = int(re.search(r'\br="(\d+)"', attrs).group(1))
            updates = cells_by_row.pop(number, {})
            if updates:
                cells = {}
                for cell in re.finditer(r'<c\b[^>]*(?:/>|>.*?</c>)', body, re.S):
                    address = re.search(r'\br="([A-Z]+\d+)"', cell[0]).group(1)
                    cells[address] = fill_cell(address, updates.pop(address), cell[0]) if address in updates else cell[0]
                cells.update({address: fill_cell(address, value) for address, value in updates.items()})
                body = "".join(cells[address] for address in sorted(cells, key=column_number))
            rows[number] = f"<row{attrs}>{body}</row>"
        for number, updates in cells_by_row.items():
            height = f' ht="{row_heights[number]}" customHeight="1"' if number in row_heights else ""
            body = "".join(fill_cell(address, updates[address]) for address in sorted(updates, key=column_number))
            rows[number] = f'<row r="{number}"{height}>{body}</row>'
        return "<sheetData>" + "".join(rows[number] for number in sorted(rows)) + "</sheetData>"

    # Patch only cells: reserializing the sheet would drop Excel extension namespaces,
    # while saving with openpyxl would discard all cached formula results.
    xml = re.sub(r"<sheetData>(.*?)</sheetData>", fill_rows, xml, count=1, flags=re.S)
    last_row = max(int(re.search(r"\d+$", address).group()) for address in values)
    xml = re.sub(
        r'(<dimension ref="[A-Z]+\d+:[A-Z]+)(\d+)("/>)',
        lambda match: match[1] + str(max(int(match[2]), last_row)) + match[3], xml, count=1,
    )
    return xml.encode("utf-8")


def _barn_calculator_excel(result):
    from decimal import Decimal
    from io import BytesIO
    from pathlib import Path
    from zipfile import ZipFile

    parameters, building = result["parameters"], result["building"]
    left, right = result["sides"]["left"], result["sides"]["right"]
    warnings = result["factual"]["warnings"] if result["factual"] else []
    summary = {
        "A2": f"Овчарня {result['barn_number']}" if result["barn_number"] else "Произвольная овчарня",
        "B2": "Фактическая компоновка" if result["composition_mode"] == "factual" else "Ручная компоновка",
        "D2": "Дата расчёта: " + date.fromisoformat(result["as_of_date"]).strftime("%d.%m.%Y"),
        "B6": Decimal(parameters["area_limit"]), "B7": Decimal(parameters["length"]),
        "B8": Decimal(parameters["central_width"]),
        "B9": "Да" if parameters["include_wall_passages"] else "Нет",
        "B10": Decimal(parameters["wall_passage_width"]), "B11": Decimal(parameters["housing_width"]),
        "B12": Decimal(parameters["breeding_premium_percent"]) / 100,
        "B13": 1, "B14": Decimal(parameters["door_width"]),
        "B15": "Свободный доступ (2 головы на место)" if parameters["feeding_mode"] == "free_access" else "Нормированное кормление (1 голова на место)",
        "G4": "2 — фиксированное число по сторонам", "G5": left["doors"], "G6": right["doors"],
        "G7": left["sections_required"], "G8": right["sections_required"],
        "G9": left["doors"], "G10": right["doors"],
        "F11": "Учтено голов", "G11": result["total_heads"],
        "F12": "Не включено в расчёт", "G12": len(warnings),
        "B18": building["max_width"], "B19": building["width"], "B20": building["area"],
        "B21": building["area_remaining"], "B22": building["central_passage_area"],
        "B23": building["wall_passages_area"],
        "B24": left["area_available"], "B25": left["area_required"], "B26": left["area_remaining"],
        "B27": right["area_available"], "B28": right["area_required"], "B29": right["area_remaining"],
        "B30": left["doors"], "B31": left["door_deduction"], "B32": left["feeding_available"],
        "B33": left["feeding_required"], "B34": left["feeding_remaining"],
        "B35": right["doors"], "B36": right["door_deduction"], "B37": right["feeding_available"],
        "B38": right["feeding_required"], "B39": right["feeding_remaining"],
        "B40": "ПРОХОДИТ" if result["passed"] else "НЕ ПРОХОДИТ",
        "A62": "Пожарно-эвакуационная проверка в калькулятор не включена. Число дверей определяется по выбранному режиму: по числу секций или вручную для каждой стороны. Все дверные проемы вычитаются из кормовой линии, поскольку выходят в центральный кормовой проход.",
    }
    styles, row_heights, formulas = {}, {}, {}
    if result["factual"]:
        summary.update(F13="Всего голов в базе", G13=result["factual"]["total_heads"])
    if warnings:
        summary["B40"] = "ПРОВЕРКА НЕПОЛНАЯ" if result["passed"] is None else "НЕ ПРОХОДИТ"
        formulas["B40"] = 'IF(AND(B21>=0,B26>=0,B29>=0,B34>=0,B39>=0),IF($G$12>0,"ПРОВЕРКА НЕПОЛНАЯ","ПРОХОДИТ"),"НЕ ПРОХОДИТ")'
        summary["A65"] = "Животные, не включённые в расчёт"
        styles["A65"] = 1
        row_heights[65] = 30
        for column, label in zip("ABCD", ("Бирка", "Тип животного", "Овчарня", "Причина")):
            summary[f"{column}66"] = label
            styles[f"{column}66"] = 1
        names = {"sheep": "Овцематка", "ewe": "Ярка", "ram": "Баранчик", "maker": "Баран-производитель"}
        for number, warning in enumerate(warnings, 67):
            values = (warning["tag_number"], names.get(warning["animal_type"], warning["animal_type"]), warning["place"], warning["reason"])
            row_heights[number] = 60
            for column, value in zip("ABCD", values):
                summary[f"{column}{number}"] = value
                styles[f"{column}{number}"] = 4
    composition, norms = {}, {}
    for number, group in enumerate(result["rows"], 2):
        lvalues, rvalues = group["left"], group["right"]
        values = [lvalues["heads"], rvalues["heads"], lvalues["area"], rvalues["area"],
                  lvalues["feeding"], rvalues["feeding"], lvalues["sections"], rvalues["sections"],
                  lvalues["sections"], rvalues["sections"],
                  f'{lvalues["sections"]} секц. слева / {rvalues["sections"]} справа; {lvalues["sections"]} дверей слева / {rvalues["sections"]} справа' if lvalues["heads"] + rvalues["heads"] else "",
                  group["area_norm"], group["front_norm"], group["section_limit"]]
        composition.update({f"{column}{number}": value for column, value in zip("BCDEFGHIJKLMNO", values)})
        norms.update({f"C{number}": group["area_norm"], f"F{number}": group["front_norm"]})
        if group["key"] in {"fattening_adults", "fattening_young"}:
            norms[f"E{number}"] = 2 if parameters["feeding_mode"] == "free_access" else 1
        summary_values = [group["label"], lvalues["heads"], rvalues["heads"], lvalues["heads"] + rvalues["heads"],
                          lvalues["area"], rvalues["area"], lvalues["feeding"], rvalues["feeding"], "—"]
        summary.update({f"{column}{number + 44}": value for column, value in zip("ABCDEFGHI", summary_values)})
    composition.update({
        f"{column}16": result["sides"][side][key]
        for column, (side, key) in zip("BCDEFGHIJK", (
            ("left", "heads"), ("right", "heads"), ("left", "area_required"), ("right", "area_required"),
            ("left", "feeding_required"), ("right", "feeding_required"), ("left", "sections_required"), ("right", "sections_required"),
            ("left", "sections_required"), ("right", "sections_required"),
        ))
    })
    summary.update({
        "B59": left["heads"], "C59": right["heads"], "D59": result["total_heads"],
        "E59": left["area_required"], "F59": right["area_required"],
        "G59": left["feeding_required"], "H59": right["feeding_required"],
        "I59": f'{left["doors"]} / {right["doors"]}',
    })
    template = Path(__file__).with_name("excel_templates") / "barn_calculator.xlsx"
    output = BytesIO()
    with ZipFile(template) as source, ZipFile(output, "w") as target:
        for part in source.infolist():
            content = source.read(part.filename)
            if part.filename == "xl/worksheets/sheet1.xml":
                content = _barn_calculator_fill_sheet(content.decode("utf-8"), summary, styles=styles, row_heights=row_heights, formulas=formulas)
            elif part.filename in {"xl/worksheets/sheet2.xml", "xl/worksheets/sheet3.xml"}:
                values = composition if part.filename.endswith("sheet2.xml") else norms
                content = _barn_calculator_fill_sheet(content.decode("utf-8"), values)
            elif part.filename == "xl/workbook.xml":
                content = re.sub(r"<calcPr\b[^>]*/>", '<calcPr calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/>', content.decode("utf-8")).encode("utf-8")
            target.writestr(part, content)
    return output.getvalue()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def barn_calculator_export(request):
    try:
        result = _barn_calculator_result(_barn_calculator_payload(request))
    except CalculatorInputError as exc:
        return Response({"error": str(exc)}, status=400)
    response = HttpResponse(_barn_calculator_excel(result), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    barn = result["barn_number"] or "custom"
    response["Content-Disposition"] = f'attachment; filename="calculator_{barn}.xlsx"'
    return response
