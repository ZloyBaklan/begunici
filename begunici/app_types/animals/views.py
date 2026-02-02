from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view
from rest_framework.permissions import AllowAny
from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import Http404, HttpResponse

from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase, CalendarNote
from .serializers import (
    MakerSerializer,
    MakerChildSerializer,
    RamSerializer,
    RamChildSerializer,
    EweSerializer,
    EweChildSerializer,
    SheepSerializer,
    SheepChildSerializer,
    LambingSerializer,
    ArchiveAnimalSerializer,
    UniversalChildSerializer,
    CalendarNoteSerializer,
)
from .backup_utils import backup_manager
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, Q
from datetime import datetime, timedelta

from begunici.app_types.veterinary.vet_models import (
    WeightRecord,
    Veterinary,
    PlaceMovement,
    Tag,
    StatusHistory,
    Status,
)
from begunici.app_types.veterinary.vet_serializers import (
    WeightRecordSerializer,
    VeterinarySerializer,
    PlaceMovementSerializer,
    StatusHistorySerializer,
)


class PaginationSetting(PageNumberPagination):
    page_size = 10  # Количество записей на странице
    page_size_query_param = "page_size"  # Возможность менять размер страницы
    max_page_size = 100  # Максимальное количество записей на странице


class AnimalBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter]
    pagination_class = PaginationSetting  # Добавляем пагинацию

    def handle_exception(self, exc):
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class MakerViewSet(viewsets.ModelViewSet):
    queryset = Maker.objects.filter(is_archived=False).order_by(
        "id"
    )  # Убедитесь, что порядок задан
    serializer_class = MakerSerializer
    filter_backends = [SearchFilter]
    search_fields = [
        "tag__tag_number",
        "animal_status__status_type",
        "place__sheepfold",
    ]
    pagination_class = PaginationSetting  # Добавляем пагинацию

    def get_object(self):
        print(f"DEBUG: self.kwargs содержат: {self.kwargs}")  # Логируем входные данные
        tag_number = self.kwargs["pk"]
        print(f"Получен tag_number из URL: {tag_number}")  # Логируем значение
        """
        Переопределяем метод, чтобы искать объект по `tag_number`, а не по `pk`.
        """
        return Maker.objects.get(tag__tag_number=tag_number)

    @action(detail=True, methods=["post"], url_path="update_working_condition")
    def update_working_condition(self, request, pk=None):
        """
        Обновление рабочего состояния производителя с установкой даты.
        """
        try:
            maker = self.get_object()
            new_condition = request.data.get("working_condition")
            if not new_condition:
                return Response(
                    {"error": "Не указано новое рабочее состояние."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Вызываем метод модели для обновления состояния
            maker.update_working_condition(new_condition)

            # Сериализуем и возвращаем обновлённый объект
            serializer = self.get_serializer(maker)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return self.handle_exception(e)

    @action(detail=True, methods=["post"], url_path="add_weight")
    def add_weight(self, request, pk=None):
        maker = self.get_object()
        weight_data = {
            "tag_number": maker.tag,
            "weight": request.data.get("weight"),
            "weight_date": request.data.get("date"),
        }
        serializer = WeightRecordSerializer(data=weight_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="add_vet_care")
    def add_vet_care(self, request, pk=None):
        maker = self.get_object()
        vet_data = {
            "tag_number": maker,
            "care_type": request.data.get("care_type"),
            "care_name": request.data.get("care_name"),
            "medication": request.data.get("medication"),
            "purpose": request.data.get("purpose"),
            "date_of_care": request.data.get("date_of_care"),
        }
        serializer = VeterinarySerializer(data=vet_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="weight_history")
    def weight_history(self, request, pk=None):
        maker = self.get_object()
        history = WeightRecord.objects.filter(
            tag__tag_number=maker.tag.tag_number
        ).order_by("-weight_date")
        serializer = WeightRecordSerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="vet_history")
    def vet_history(self, request, pk=None):
        """
        Получаем историю ветобработок для животного.
        """

        maker = self.get_object()
        vet_history = (
            Veterinary.objects.filter(tag__tag_number=maker.tag.tag_number)
            .select_related("veterinary_care")
            .order_by("-date_of_care")
        )
        # Применяем пагинацию
        page = self.paginate_queryset(vet_history)
        if page is not None:
            serializer = VeterinarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Если пагинация не настроена, возвращаем все записи (лучше избегать этого)
        serializer = VeterinarySerializer(vet_history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="place_history")
    def place_history(self, request, pk=None):
        """
        Возвращает историю перемещений для конкретного животного с поддержкой пагинации.
        """
        maker = self.get_object()  # Получаем объект Maker по tag_number
        place_movements = PlaceMovement.objects.filter(
            tag__tag_number=maker.tag.tag_number
        ).order_by("-new_place__date_of_transfer")

        # Применяем пагинацию
        page = self.paginate_queryset(place_movements)
        if page is not None:
            serializer = PlaceMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Если пагинация не настроена, возвращаем все записи (лучше избегать этого)
        serializer = PlaceMovementSerializer(place_movements, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="status_history")
    def status_history(self, request, pk=None):
        """
        Возвращает историю статусов для конкретного животного с поддержкой пагинации.
        """
        maker = self.get_object()  # Получаем объект Maker
        status_history = StatusHistory.objects.filter(
            tag__tag_number=maker.tag.tag_number
        ).order_by("-change_date")

        # Применяем пагинацию
        page = self.paginate_queryset(status_history)
        if page is not None:
            serializer = StatusHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # Если пагинация не настроена, возвращаем все записи (не рекомендуется)
        serializer = StatusHistorySerializer(status_history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Дети
    @action(detail=True, methods=["get"], url_path="children")
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

    @action(detail=True, methods=["post"], url_path="add_place_movement")
    def add_place_movement(self, request, pk=None):
        maker = self.get_object()
        movement_data = {
            "tag_number": maker.tag.tag_number,
            "old_place": request.data.get("old_place"),
            "new_place": request.data.get("new_place"),
            "date_of_transfer": request.data.get("new_place__date_of_transfer"),
        }
        serializer = PlaceMovementSerializer(data=movement_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="api")
    def retrieve_api(self, request, pk=None):
        maker = self.get_object()
        serializer = self.get_serializer(maker)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="family_tree")
    def family_tree(self, request, pk=None):
        """
        Получаем родителей и детей для животного.
        """
        maker = self.get_object()
        father = maker.father
        mother = maker.mother
        children = maker.get_children()  # Используем исправленный метод

        data = {
            "father": MakerSerializer(father).data if father else None,
            "mother": MakerSerializer(mother).data if mother else None,
            "children": MakerSerializer(children, many=True).data,
        }
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="update_parents")
    def update_parents(self, request, pk=None):
        maker = self.get_object()

        mother_tag_number = request.data.get("mother_tag_number")
        father_tag_number = request.data.get("father_tag_number")

        # Обработка мамы
        if mother_tag_number:
            try:
                mother_tag = Tag.objects.get(tag_number=mother_tag_number)
                maker.mother = mother_tag
            except Tag.DoesNotExist:
                return Response(
                    {"error": f"Mother tag {mother_tag_number} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif mother_tag_number is None:
            maker.mother = None  # Если явно передан null, удаляем маму

        # Обработка папы
        if father_tag_number:
            try:
                father_tag = Tag.objects.get(tag_number=father_tag_number)
                maker.father = father_tag
            except Tag.DoesNotExist:
                return Response(
                    {"error": f"Father tag {father_tag_number} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif father_tag_number is None:
            maker.father = None  # Если явно передан null, удаляем папу

        maker.save()

        return Response(
            {"success": "Parents updated successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        """Восстановление производителя из архива"""
        maker = self.get_object()
        
        # Находим активный статус (не архивный)
        try:
            active_status = Status.objects.filter(
                status_type__in=["Активный", "Здоровый", "Рабочий"]
            ).first()
            if not active_status:
                # Если нет подходящего статуса, берем любой неархивный
                active_status = Status.objects.exclude(
                    status_type__in=["Убыл", "Убой", "Продажа"]
                ).first()
            
            if active_status:
                maker.animal_status = active_status
            
            maker.is_archived = False
            maker.save()
            
            return Response({"success": "Maker restored from archive"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RamViewSet(AnimalBaseViewSet):
    queryset = Ram.objects.filter(is_archived=False).order_by("id")
    serializer_class = RamSerializer
    filter_backends = [SearchFilter]
    search_fields = [
        "tag__tag_number",
        "animal_status__status_type",
        "place__sheepfold",
    ]
    pagination_class = PaginationSetting

    def get_object(self):
        print(f"DEBUG: self.kwargs содержат: {self.kwargs}")
        tag_number = self.kwargs["pk"]
        print(f"Получен tag_number из URL: {tag_number}")
        """
        Переопределяем метод, чтобы искать объект по `tag_number`, а не по `pk`.
        """
        return Ram.objects.get(tag__tag_number=tag_number)

    @action(detail=True, methods=["get"], url_path="family_tree")
    def family_tree(self, request, pk=None):
        ram = self.get_object()
        data = {
            "animal": RamSerializer(ram).data,
            "mother": RamSerializer(ram.mother.ram_set.first()).data if ram.mother and hasattr(ram.mother, 'ram_set') and ram.mother.ram_set.exists() else None,
            "father": MakerSerializer(ram.father.maker_set.first()).data if ram.father and hasattr(ram.father, 'maker_set') and ram.father.maker_set.exists() else None,
        }
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="update_parents")
    def update_parents(self, request, pk=None):
        ram = self.get_object()

        mother_tag_number = request.data.get("mother_tag_number")
        father_tag_number = request.data.get("father_tag_number")

        # Обработка мамы
        if mother_tag_number:
            try:
                mother_tag = Tag.objects.get(tag_number=mother_tag_number)
                ram.mother = mother_tag
            except Tag.DoesNotExist:
                return Response(
                    {"error": f"Mother tag {mother_tag_number} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif mother_tag_number is None:
            ram.mother = None

        # Обработка папы
        if father_tag_number:
            try:
                father_tag = Tag.objects.get(tag_number=father_tag_number)
                ram.father = father_tag
            except Tag.DoesNotExist:
                return Response(
                    {"error": f"Father tag {father_tag_number} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif father_tag_number is None:
            ram.father = None

        ram.save()

        return Response(
            {"success": "Parents updated successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["get"], url_path="children")
    def children(self, request, pk=None):
        ram = self.get_object()
        children = ram.get_children()
        # Применяем пагинацию
        page = self.paginate_queryset(children)
        if page is not None:
            serializer = RamChildSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(RamChildSerializer(children, many=True).data)

    @action(detail=True, methods=["get"], url_path="status_history")
    def status_history(self, request, pk=None):
        ram = self.get_object()
        status_history = StatusHistory.objects.filter(tag=ram.tag).order_by("-change_date")
        # Применяем пагинацию
        page = self.paginate_queryset(status_history)
        if page is not None:
            serializer = StatusHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(StatusHistorySerializer(status_history, many=True).data)

    @action(detail=True, methods=["get"], url_path="place_history")
    def place_history(self, request, pk=None):
        ram = self.get_object()
        place_movements = PlaceMovement.objects.filter(tag=ram.tag).order_by("-new_place__date_of_transfer")
        # Применяем пагинацию
        page = self.paginate_queryset(place_movements)
        if page is not None:
            serializer = PlaceMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(PlaceMovementSerializer(place_movements, many=True).data)

    @action(detail=True, methods=["get"], url_path="weight_history")
    def weight_history(self, request, pk=None):
        ram = self.get_object()
        history = WeightRecord.objects.filter(
            tag__tag_number=ram.tag.tag_number
        ).order_by("-weight_date")
        serializer = WeightRecordSerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="vet_history")
    def vet_history(self, request, pk=None):
        ram = self.get_object()
        vet_history = (
            Veterinary.objects.filter(tag__tag_number=ram.tag.tag_number)
            .select_related("veterinary_care")
            .order_by("-date_of_care")
        )
        # Применяем пагинацию
        page = self.paginate_queryset(vet_history)
        if page is not None:
            serializer = VeterinarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = VeterinarySerializer(vet_history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        """Восстановление барана из архива"""
        ram = self.get_object()
        
        # Находим активный статус (не архивный)
        try:
            active_status = Status.objects.filter(
                status_type__in=["Активный", "Здоровый", "Рабочий"]
            ).first()
            if not active_status:
                # Если нет подходящего статуса, берем любой неархивный
                active_status = Status.objects.exclude(
                    status_type__in=["Убыл", "Убой", "Продажа"]
                ).first()
            
            if active_status:
                ram.animal_status = active_status
            
            ram.is_archived = False
            ram.save()
            
            return Response({"success": "Ram restored from archive"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="api")
    def retrieve_api(self, request, pk=None):
        ram = self.get_object()
        serializer = self.get_serializer(ram)
        return Response(serializer.data)


class EweViewSet(AnimalBaseViewSet):
    queryset = Ewe.objects.filter(is_archived=False).order_by("id")
    serializer_class = EweSerializer
    filter_backends = [SearchFilter]
    search_fields = [
        "tag__tag_number",
        "animal_status__status_type",
        "place__sheepfold",
    ]
    pagination_class = PaginationSetting

    def get_object(self):
        print(f"DEBUG: self.kwargs содержат: {self.kwargs}")
        tag_number = self.kwargs["pk"]
        print(f"Получен tag_number из URL: {tag_number}")
        """
        Переопределяем метод, чтобы искать объект по `tag_number`, а не по `pk`.
        """
        return Ewe.objects.get(tag__tag_number=tag_number)

    @action(detail=True, methods=["post"], url_path="to_sheep")
    def to_sheep(self, request, pk=None):
        try:
            ewe = self.get_object()
            sheep = ewe.to_sheep()
            return Response(
                {
                    "status": "Ярка преобразована в овцу",
                    "new_sheep": SheepSerializer(sheep).data,
                }
            )
        except Exception as e:
            return self.handle_exception(e)

    @action(detail=True, methods=["get"], url_path="family_tree")
    def family_tree(self, request, pk=None):
        ewe = self.get_object()
        data = {
            "animal": EweSerializer(ewe).data,
            "mother": SheepSerializer(ewe.mother.sheep_set.first()).data if ewe.mother and hasattr(ewe.mother, 'sheep_set') and ewe.mother.sheep_set.exists() else None,
            "father": MakerSerializer(ewe.father.maker_set.first()).data if ewe.father and hasattr(ewe.father, 'maker_set') and ewe.father.maker_set.exists() else None,
        }
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="update_parents")
    def update_parents(self, request, pk=None):
        ewe = self.get_object()

        mother_tag_number = request.data.get("mother_tag_number")
        father_tag_number = request.data.get("father_tag_number")

        # Обработка мамы
        if mother_tag_number:
            try:
                mother_tag = Tag.objects.get(tag_number=mother_tag_number)
                ewe.mother = mother_tag
            except Tag.DoesNotExist:
                return Response(
                    {"error": f"Mother tag {mother_tag_number} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif mother_tag_number is None:
            ewe.mother = None

        # Обработка папы
        if father_tag_number:
            try:
                father_tag = Tag.objects.get(tag_number=father_tag_number)
                ewe.father = father_tag
            except Tag.DoesNotExist:
                return Response(
                    {"error": f"Father tag {father_tag_number} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif father_tag_number is None:
            ewe.father = None

        ewe.save()

        return Response(
            {"success": "Parents updated successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["get"], url_path="children")
    def children(self, request, pk=None):
        ewe = self.get_object()
        children = ewe.get_children()
        # Применяем пагинацию
        page = self.paginate_queryset(children)
        if page is not None:
            serializer = EweChildSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(EweChildSerializer(children, many=True).data)

    @action(detail=True, methods=["get"], url_path="status_history")
    def status_history(self, request, pk=None):
        ewe = self.get_object()
        status_history = StatusHistory.objects.filter(tag=ewe.tag).order_by("-change_date")
        # Применяем пагинацию
        page = self.paginate_queryset(status_history)
        if page is not None:
            serializer = StatusHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(StatusHistorySerializer(status_history, many=True).data)

    @action(detail=True, methods=["get"], url_path="place_history")
    def place_history(self, request, pk=None):
        ewe = self.get_object()
        place_movements = PlaceMovement.objects.filter(tag=ewe.tag).order_by("-new_place__date_of_transfer")
        # Применяем пагинацию
        page = self.paginate_queryset(place_movements)
        if page is not None:
            serializer = PlaceMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(PlaceMovementSerializer(place_movements, many=True).data)

    @action(detail=True, methods=["get"], url_path="weight_history")
    def weight_history(self, request, pk=None):
        ewe = self.get_object()
        history = WeightRecord.objects.filter(
            tag__tag_number=ewe.tag.tag_number
        ).order_by("-weight_date")
        serializer = WeightRecordSerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="vet_history")
    def vet_history(self, request, pk=None):
        ewe = self.get_object()
        vet_history = (
            Veterinary.objects.filter(tag__tag_number=ewe.tag.tag_number)
            .select_related("veterinary_care")
            .order_by("-date_of_care")
        )
        # Применяем пагинацию
        page = self.paginate_queryset(vet_history)
        if page is not None:
            serializer = VeterinarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = VeterinarySerializer(vet_history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        """Восстановление ярки из архива"""
        ewe = self.get_object()
        
        # Находим активный статус (не архивный)
        try:
            active_status = Status.objects.filter(
                status_type__in=["Активный", "Здоровый", "Рабочий"]
            ).first()
            if not active_status:
                # Если нет подходящего статуса, берем любой неархивный
                active_status = Status.objects.exclude(
                    status_type__in=["Убыл", "Убой", "Продажа"]
                ).first()
            
            if active_status:
                ewe.animal_status = active_status
            
            ewe.is_archived = False
            ewe.save()
            
            return Response({"success": "Ewe restored from archive"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="api")
    def retrieve_api(self, request, pk=None):
        ewe = self.get_object()
        serializer = self.get_serializer(ewe)
        return Response(serializer.data)


class SheepViewSet(AnimalBaseViewSet):
    queryset = Sheep.objects.filter(is_archived=False).order_by("id")
    serializer_class = SheepSerializer
    filter_backends = [SearchFilter]
    search_fields = [
        "tag__tag_number",
        "animal_status__status_type",
        "place__sheepfold",
    ]
    pagination_class = PaginationSetting

    def get_object(self):
        print(f"DEBUG: self.kwargs содержат: {self.kwargs}")
        tag_number = self.kwargs["pk"]
        print(f"Получен tag_number из URL: {tag_number}")
        """
        Переопределяем метод, чтобы искать объект по `tag_number`, а не по `pk`.
        """
        return Sheep.objects.get(tag__tag_number=tag_number)

    @action(detail=True, methods=["post"], url_path="add_lambing")
    def add_lambing(self, request, pk=None):
        sheep = self.get_object()
        maker = Maker.objects.get(tag__tag_number=request.data.get("maker_id"))
        lambing = sheep.add_lambing(
            maker=maker,
            actual_lambing_date=request.data.get("actual_lambing_date"),
            lambs_data=request.data.get("lambs_data"),
        )
        return Response(LambingSerializer(lambing).data)

    @action(detail=True, methods=["get"], url_path="family_tree")
    def family_tree(self, request, pk=None):
        sheep = self.get_object()
        data = {
            "animal": SheepSerializer(sheep).data,
            "mother": SheepSerializer(sheep.mother.sheep_set.first()).data if sheep.mother and hasattr(sheep.mother, 'sheep_set') and sheep.mother.sheep_set.exists() else None,
            "father": MakerSerializer(sheep.father.maker_set.first()).data if sheep.father and hasattr(sheep.father, 'maker_set') and sheep.father.maker_set.exists() else None,
        }
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="update_parents")
    def update_parents(self, request, pk=None):
        sheep = self.get_object()

        mother_tag_number = request.data.get("mother_tag_number")
        father_tag_number = request.data.get("father_tag_number")

        # Обработка мамы
        if mother_tag_number:
            try:
                mother_tag = Tag.objects.get(tag_number=mother_tag_number)
                sheep.mother = mother_tag
            except Tag.DoesNotExist:
                return Response(
                    {"error": f"Mother tag {mother_tag_number} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif mother_tag_number is None:
            sheep.mother = None

        # Обработка папы
        if father_tag_number:
            try:
                father_tag = Tag.objects.get(tag_number=father_tag_number)
                sheep.father = father_tag
            except Tag.DoesNotExist:
                return Response(
                    {"error": f"Father tag {father_tag_number} not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif father_tag_number is None:
            sheep.father = None

        sheep.save()

        return Response(
            {"success": "Parents updated successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["get"], url_path="children")
    def children(self, request, pk=None):
        sheep = self.get_object()
        children = sheep.get_children()
        # Применяем пагинацию
        page = self.paginate_queryset(children)
        if page is not None:
            serializer = SheepChildSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(SheepChildSerializer(children, many=True).data)

    @action(detail=True, methods=["get"], url_path="status_history")
    def status_history(self, request, pk=None):
        sheep = self.get_object()
        status_history = StatusHistory.objects.filter(tag=sheep.tag).order_by("-change_date")
        # Применяем пагинацию
        page = self.paginate_queryset(status_history)
        if page is not None:
            serializer = StatusHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(StatusHistorySerializer(status_history, many=True).data)

    @action(detail=True, methods=["get"], url_path="place_history")
    def place_history(self, request, pk=None):
        sheep = self.get_object()
        place_movements = PlaceMovement.objects.filter(tag=sheep.tag).order_by("-new_place__date_of_transfer")
        # Применяем пагинацию
        page = self.paginate_queryset(place_movements)
        if page is not None:
            serializer = PlaceMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(PlaceMovementSerializer(place_movements, many=True).data)

    @action(detail=True, methods=["get"], url_path="weight_history")
    def weight_history(self, request, pk=None):
        sheep = self.get_object()
        history = WeightRecord.objects.filter(
            tag__tag_number=sheep.tag.tag_number
        ).order_by("-weight_date")
        serializer = WeightRecordSerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="vet_history")
    def vet_history(self, request, pk=None):
        sheep = self.get_object()
        vet_history = (
            Veterinary.objects.filter(tag__tag_number=sheep.tag.tag_number)
            .select_related("veterinary_care")
            .order_by("-date_of_care")
        )
        # Применяем пагинацию
        page = self.paginate_queryset(vet_history)
        if page is not None:
            serializer = VeterinarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = VeterinarySerializer(vet_history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        """Восстановление овцы из архива"""
        sheep = self.get_object()
        
        # Находим активный статус (не архивный)
        try:
            active_status = Status.objects.filter(
                status_type__in=["Активный", "Здоровый", "Рабочий"]
            ).first()
            if not active_status:
                # Если нет подходящего статуса, берем любой неархивный
                active_status = Status.objects.exclude(
                    status_type__in=["Убыл", "Убой", "Продажа"]
                ).first()
            
            if active_status:
                sheep.animal_status = active_status
            
            sheep.is_archived = False
            sheep.save()
            
            return Response({"success": "Sheep restored from archive"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="api")
    def retrieve_api(self, request, pk=None):
        sheep = self.get_object()
        serializer = self.get_serializer(sheep)
        return Response(serializer.data)


class LambingViewSet(viewsets.ModelViewSet):
    queryset = Lambing.objects.all().order_by('-start_date')
    serializer_class = LambingSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter]
    search_fields = ['sheep__tag__tag_number', 'ewe__tag__tag_number', 'maker__tag__tag_number', 'ram__tag__tag_number']
    pagination_class = PaginationSetting

    def get_queryset(self):
        """Фильтрация по активности окота"""
        queryset = super().get_queryset()
        is_active = self.request.query_params.get('is_active', None)
        
        if is_active is not None:
            if is_active.lower() == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active.lower() == 'false':
                queryset = queryset.filter(is_active=False)
        
        return queryset

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_lambing(self, request, pk=None):
        """Завершить окот (простое завершение без детей)"""
        try:
            lambing = self.get_object()
            lambing.complete_lambing()
            return Response(
                {"success": "Окот завершен"}, 
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'], url_path='complete-with-children')
    def complete_lambing_with_children(self, request, pk=None):
        """Завершить окот с созданием детей"""
        try:
            from datetime import datetime
            
            lambing = self.get_object()
            
            # Получаем данные из запроса
            actual_date_str = request.data.get('actual_lambing_date')
            number_of_lambs = request.data.get('number_of_lambs', 0)
            note = request.data.get('note', '')
            lambs_data = request.data.get('lambs', [])
            new_mother_status_id = request.data.get('new_mother_status_id')  # Новый статус для матери
            
            if not actual_date_str:
                return Response(
                    {"error": "Необходимо указать дату фактических родов"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Преобразуем строку даты в объект date
            try:
                actual_date = datetime.strptime(actual_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Неверный формат даты. Используйте YYYY-MM-DD"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Обновляем данные окота
            lambing.actual_lambing_date = actual_date
            lambing.number_of_lambs = number_of_lambs
            if note:
                lambing.note = note
            lambing.is_active = False
            
            # Устанавливаем новый статус матери, если он указан
            mother = lambing.get_mother()
            if mother and new_mother_status_id:
                try:
                    new_status = Status.objects.get(id=new_mother_status_id)
                    mother.animal_status = new_status
                    mother.save()
                except Status.DoesNotExist:
                    return Response(
                        {"error": "Указанный статус не найден"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                except Exception as e:
                    print(f"Ошибка при установке нового статуса матери: {e}")
            
            lambing.save()
            
            # Если мать - ярка, преобразуем её в овцу после первого окота
            mother = lambing.get_mother()
            if mother and lambing.get_mother_type() == "Ярка":
                # Преобразуем ярку в овцу
                sheep = mother.to_sheep()
                # Обновляем связь окота с новой овцой
                lambing.sheep = sheep
                lambing.ewe = None
                lambing.save()
                # Обновляем переменную mother для дальнейшего использования
                mother = sheep
            
            # Создаем детей, если они указаны
            created_children = []
            father = lambing.get_father()
            
            for lamb_data in lambs_data:
                try:
                    # Создаем бирку для ребенка
                    tag, created = Tag.objects.get_or_create(
                        tag_number=lamb_data['tag_number']
                    )
                    
                    if not created:
                        return Response(
                            {"error": f"Бирка {lamb_data['tag_number']} уже используется"}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Определяем тип животного и создаем его
                    if lamb_data['gender'] == 'male':
                        # Создаем барана
                        child = Ram.objects.create(
                            tag=tag,
                            birth_date=actual_date,
                            mother=mother.tag if mother else None,
                            father=father.tag if father else None,
                            animal_status_id=lamb_data.get('animal_status_id'),
                            place_id=lamb_data.get('place_id'),
                            note=lamb_data.get('note', '')
                        )
                        tag.animal_type = 'Ram'
                    else:
                        # Создаем ярку
                        child = Ewe.objects.create(
                            tag=tag,
                            birth_date=actual_date,
                            mother=mother.tag if mother else None,
                            father=father.tag if father else None,
                            animal_status_id=lamb_data.get('animal_status_id'),
                            place_id=lamb_data.get('place_id'),
                            note=lamb_data.get('note', '')
                        )
                        tag.animal_type = 'Ewe'
                    
                    tag.save()
                    created_children.append({
                        'tag_number': tag.tag_number,
                        'type': tag.animal_type,
                        'gender': lamb_data['gender']
                    })
                    
                except Exception as child_error:
                    return Response(
                        {"error": f"Ошибка создания ягненка {lamb_data['tag_number']}: {str(child_error)}"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return Response({
                "success": "Окот завершен",
                "created_children": created_children,
                "lambing": LambingSerializer(lambing).data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='calendar')
    def calendar_data(self, request):
        """Получить данные для календаря ожидаемых родов"""
        try:
            # Получаем только активные окоты
            active_lambings = Lambing.objects.filter(is_active=True)
            
            calendar_data = {}
            for lambing in active_lambings:
                date_str = lambing.planned_lambing_date.strftime('%Y-%m-%d')
                mother = lambing.get_mother()
                
                if date_str not in calendar_data:
                    calendar_data[date_str] = []
                
                calendar_data[date_str].append({
                    'id': lambing.id,
                    'mother_tag': mother.tag.tag_number if mother and mother.tag else 'Неизвестно',
                    'mother_type': lambing.get_mother_type(),
                    'father_tag': lambing.get_father().tag.tag_number if lambing.get_father() and lambing.get_father().tag else 'Неизвестно',
                    'father_type': lambing.get_father_type(),
                    'start_date': lambing.start_date.strftime('%Y-%m-%d')
                })
            
            return Response(calendar_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='by-animal')
    def by_animal(self, request):
        """Получить окоты для конкретного животного"""
        animal_type = request.query_params.get('animal_type')
        tag_number = request.query_params.get('tag_number')
        
        if not animal_type or not tag_number:
            return Response(
                {"error": "Необходимо указать animal_type и tag_number"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if animal_type == 'sheep':
                animal = Sheep.objects.get(tag__tag_number=tag_number)
                lambings = Lambing.objects.filter(sheep=animal).order_by('-start_date')
            elif animal_type == 'ewe':
                animal = Ewe.objects.get(tag__tag_number=tag_number)
                lambings = Lambing.objects.filter(ewe=animal).order_by('-start_date')
            else:
                return Response(
                    {"error": "Неподдерживаемый тип животного"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = self.get_serializer(lambings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except (Sheep.DoesNotExist, Ewe.DoesNotExist):
            return Response(
                {"error": "Животное не найдено"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class CalendarNoteViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления заметками календаря
    """
    queryset = CalendarNote.objects.all().order_by('-date')
    serializer_class = CalendarNoteSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['text']
    ordering_fields = ['date', 'created_at']
    pagination_class = PaginationSetting

    def get_queryset(self):
        """Фильтрация заметок по дате"""
        queryset = super().get_queryset()
        date = self.request.query_params.get('date', None)
        
        if date:
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                queryset = queryset.filter(date=date_obj)
            except ValueError:
                pass  # Игнорируем неверный формат даты
        
        return queryset

    @action(detail=False, methods=['get'], url_path='by-week')
    def by_week(self, request):
        """Получить заметки для недели"""
        from datetime import datetime, timedelta
        
        date_str = request.query_params.get('date')
        if not date_str:
            return Response(
                {"error": "Необходимо указать дату"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Переданная дата уже должна быть понедельником
            start_of_week = date_obj
            if date_obj.weekday() != 0:  # Если не понедельник
                start_of_week = date_obj - timedelta(days=date_obj.weekday())
            
            end_of_week = start_of_week + timedelta(days=6)
            
            notes = CalendarNote.objects.filter(
                date__gte=start_of_week,
                date__lte=end_of_week
            ).order_by('date')
            
            serializer = CalendarNoteSerializer(notes, many=True)
            return Response({
                'start_date': start_of_week,
                'end_date': end_of_week,
                'notes': serializer.data
            }, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response(
                {"error": "Неверный формат даты. Используйте YYYY-MM-DD"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='calendar-data')
    def calendar_data(self, request):
        """Получить данные заметок для календаря"""
        try:
            year = request.query_params.get('year')
            month = request.query_params.get('month')
            
            queryset = CalendarNote.objects.all()
            
            if year:
                queryset = queryset.filter(date__year=int(year))
            if month:
                queryset = queryset.filter(date__month=int(month))
            
            # Группируем заметки по датам
            calendar_data = {}
            for note in queryset:
                date_str = note.date.strftime('%Y-%m-%d')
                if date_str not in calendar_data:
                    calendar_data[date_str] = []
                
                calendar_data[date_str].append({
                    'id': note.id,
                    'text': note.text[:100] + '...' if len(note.text) > 100 else note.text,
                    'formatted_text': note.get_formatted_text()
                })
            
            return Response(calendar_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class MakersView(TemplateView):
    template_name = "makers.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class AnimalDetailView(TemplateView):
    template_name = "animal_detail.html" # Унифицированный шаблон
    model = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag_number = self.kwargs.get("tag_number")
        try:
            animal = self.model.objects.get(tag__tag_number=tag_number)
            context["animal"] = animal
            context["animal_type"] = self.model._meta.model_name
        except self.model.DoesNotExist:
            raise Http404(f"{self.model._meta.verbose_name.capitalize()} не найден")
        return context

class MakerDetailView(AnimalDetailView):
    model = Maker

class RamDetailView(AnimalDetailView):
    model = Ram

class EweDetailView(AnimalDetailView):
    model = Ewe

class SheepDetailView(AnimalDetailView):
    model = Sheep


class AnimalAnalyticsView(TemplateView):
    template_name = "animal_analytics.html" # Унифицированный шаблон
    model = None
    serializer_class = None
    child_serializer_class = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag_number = self.kwargs.get("tag_number")
        
        try:
            animal = self.model.objects.get(tag__tag_number=tag_number)
        except self.model.DoesNotExist:
            raise Http404(f"{self.model._meta.verbose_name.capitalize()} не найден")

        serialized_animal = self.serializer_class(animal).data
        children = animal.get_children()
        children_serialized = self.child_serializer_class(children, many=True).data if self.child_serializer_class else []

        context.update({
            "animal": serialized_animal,
            "animal_type": self.model._meta.model_name,
            "children": children_serialized,
            "status_history": StatusHistorySerializer(
                StatusHistory.objects.filter(tag=animal.tag).order_by("-change_date"),
                many=True
            ).data,
            "place_movements": PlaceMovementSerializer(
                PlaceMovement.objects.filter(tag=animal.tag).order_by("-new_place__date_of_transfer"),
                many=True
            ).data,
            "veterinary_history": VeterinarySerializer(
                Veterinary.objects.filter(tag=animal.tag).order_by("-date_of_care"),
                many=True
            ).data,
            "weight_records": WeightRecordSerializer(
                WeightRecord.objects.filter(tag=animal.tag).order_by("-weight_date"),
                many=True
            ).data,
        })
        return context

class MakerAnalyticsView(AnimalAnalyticsView):
    model = Maker
    serializer_class = MakerSerializer
    child_serializer_class = UniversalChildSerializer

class RamAnalyticsView(AnimalAnalyticsView):
    model = Ram
    serializer_class = RamSerializer
    child_serializer_class = UniversalChildSerializer

class EweAnalyticsView(AnimalAnalyticsView):
    model = Ewe
    serializer_class = EweSerializer
    child_serializer_class = UniversalChildSerializer

class SheepAnalyticsView(AnimalAnalyticsView):
    model = Sheep
    serializer_class = SheepSerializer
    child_serializer_class = UniversalChildSerializer  # Используем универсальный сериализатор для детей


class ArchiveView(TemplateView):
    """
    Представление для страницы архива с поддержкой фильтрации по типу животного.
    """
    template_name = "archive.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Получаем параметр type из URL
        animal_type = self.request.GET.get('type', '')
        context['animal_type'] = animal_type
        return context


class AnimalActionsViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"], url_path="bulk_archive")
    def bulk_archive(self, request):
        animal_ids = request.data.get("animal_ids", [])
        status_id = request.data.get("status_id")

        if not animal_ids or not status_id:
            return Response(
                {"error": "Необходимо указать ID животных и статус."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            archive_status = Status.objects.get(pk=status_id)
        except Status.DoesNotExist:
            return Response(
                {"error": "Указанный статус не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )

        updated_count = 0
        animal_models = [Maker, Ram, Ewe, Sheep]
        for model in animal_models:
            # Мы используем tag__id, так как animal_ids - это ID бирок
            queryset = model.objects.filter(tag__id__in=animal_ids)
            updated_count += queryset.update(animal_status=archive_status)

        return Response(
            {"success": f"Статус обновлен для {updated_count} животных."},
            status=status.HTTP_200_OK,
        )


class ArchiveViewSet(ListModelMixin, GenericViewSet):
    """
    ViewSet для общего архива животных.
    """

    serializer_class = ArchiveAnimalSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = [
        "tag__tag_number",
        "animal_status__status_type",
        "place__sheepfold",
    ]
    ordering_fields = ["birth_date", "age", "tag__tag_number"]
    pagination_class = PaginationSetting  # Добавляем пагинацию

    def get_queryset(self):
        """
        Получаем архив всех животных, объединяя модели Maker, Sheep, Ewe и Ram.
        """
        animal_type = self.request.query_params.get("type", None)

        if animal_type == "Maker":
            return Maker.objects.filter(is_archived=True)
        elif animal_type == "Sheep":
            return Sheep.objects.filter(is_archived=True)
        elif animal_type == "Ewe":
            return Ewe.objects.filter(is_archived=True)
        elif animal_type == "Ram":
            return Ram.objects.filter(is_archived=True)

        # Объединение всех архивированных животных в один список
        makers = Maker.objects.filter(is_archived=True)
        sheep = Sheep.objects.filter(is_archived=True)
        ewes = Ewe.objects.filter(is_archived=True)
        rams = Ram.objects.filter(is_archived=True)

        # Объединяем QuerySet'ы
        queryset = list(makers) + list(sheep) + list(ewes) + list(rams)
        return queryset


# Представления для страниц


def animals(request):
    return render(request, "animals.html")


def create_animal(request):
    return render(request, "create_animal.html")


# API для экспорта в Excel

@api_view(['POST'])
def export_to_excel(request):
    # Пробуем импортировать openpyxl, если не получается - используем CSV
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter
        use_excel = True
        print("Используем Excel формат (openpyxl)")
    except ImportError as e:
        print(f"openpyxl не доступен: {e}. Используем CSV формат.")
        use_excel = False
        import csv
        import io
    
    try:
        """
        Экспорт животных в Excel с фильтрами:
        - animal_type: 'maker', 'ram', 'ewe', 'sheep'
        - limit: количество животных от начала списка
        - weight_min: минимальный вес
        - weight_max: максимальный вес
        - age_min: минимальный возраст
        - age_max: максимальный возраст
        - include_details: включить родителей, детей и историю (true/false)
        """
        print(f"Получен запрос на экспорт: {request.data}")  # Отладочный вывод
        animal_type = request.data.get('animal_type', 'maker')
        limit = request.data.get('limit', None)
        weight_min = request.data.get('weight_min', None)
        weight_max = request.data.get('weight_max', None)
        age_min = request.data.get('age_min', None)
        age_max = request.data.get('age_max', None)
        include_details = request.data.get('include_details', False)
        
        print(f"Параметры экспорта: type={animal_type}, limit={limit}, weight_min={weight_min}, weight_max={weight_max}, age_min={age_min}, age_max={age_max}, include_details={include_details}")
        
        # Выбираем модель
        model_map = {
            'maker': Maker,
            'ram': Ram,
            'ewe': Ewe,
            'sheep': Sheep
        }
        
        model = model_map.get(animal_type, Maker)
        queryset = model.objects.filter(is_archived=False).order_by('id')
        
        # Применяем фильтры
        if limit:
            queryset = queryset[:int(limit)]
        
        # Фильтр по возрасту
        if age_min is not None:
            queryset = queryset.filter(age__gte=float(age_min))
        if age_max is not None:
            queryset = queryset.filter(age__lte=float(age_max))
        
        # Фильтр по весу (берём последний вес)
        animals_list = []
        for animal in queryset:
            last_weight = WeightRecord.objects.filter(tag=animal.tag).order_by('-weight_date').first()
            weight_value = float(last_weight.weight) if last_weight else None
            
            # Проверяем фильтр по весу
            if weight_min is not None and (weight_value is None or weight_value < float(weight_min)):
                continue
            if weight_max is not None and (weight_value is None or weight_value > float(weight_max)):
                continue
            
            animals_list.append({
                'animal': animal,
                'last_weight': weight_value,
                'last_weight_date': last_weight.weight_date if last_weight else None
            })
        
        print(f"Найдено {len(animals_list)} животных для экспорта")
        
        # Заголовки
        headers = ['№', 'Бирка', 'Статус', 'Возраст (мес)', 'Овчарня', 'Последний вес (кг)', 'Дата взвешивания']
        
        if animal_type == 'maker':
            headers.extend(['Племенной статус', 'Рабочее состояние'])
        
        headers.append('Примечание')
        
        if include_details:
            headers.extend(['Мать', 'Отец', 'Дети', 'История веса', 'История ветобработок'])
        
        # Подготавливаем данные для экспорта
        export_data = []
        for idx, item in enumerate(animals_list, start=1):
            animal = item['animal']
            row_data = [
                idx,  # №
                animal.tag.tag_number,
                animal.animal_status.status_type if animal.animal_status else 'Нет статуса',
                animal.age if animal.age else '-',
                animal.place.sheepfold if animal.place else 'Нет данных',
                item['last_weight'] if item['last_weight'] else '-',
                item['last_weight_date'].strftime('%Y-%m-%d') if item['last_weight_date'] else '-'
            ]
            
            if animal_type == 'maker':
                row_data.extend([
                    animal.plemstatus if hasattr(animal, 'plemstatus') else '-',
                    animal.working_condition if hasattr(animal, 'working_condition') else '-'
                ])
            
            row_data.append(animal.note if animal.note else '')
            
            if include_details:
                # Родители
                mother = animal.mother.tag_number if animal.mother else 'Нет данных'
                father = animal.father.tag_number if animal.father else 'Нет данных'
                
                # Дети
                children = animal.get_children()
                # Словарь переводов типов животных
                type_translations = {
                    'Maker': 'Производитель',
                    'Ram': 'Баран',
                    'Ewe': 'Ярка',
                    'Sheep': 'Овца'
                }
                children_str = '; '.join([
                    f"{child.tag.tag_number} ({type_translations.get(child.get_animal_type(), child.get_animal_type())}" + 
                    (f", {child.age}мес" if child.age else "") + ")"
                    for child in children[:10]  # Ограничиваем до 10 детей для читаемости
                ]) if children else 'Нет данных'
                
                # История веса
                weight_history = WeightRecord.objects.filter(tag=animal.tag).order_by('-weight_date')[:5]
                weight_str = '; '.join([f"{w.weight_date}: {w.weight}кг" for w in weight_history])
                
                # История ветобработок
                vet_history = Veterinary.objects.filter(tag=animal.tag).select_related('veterinary_care').order_by('-date_of_care')[:5]
                vet_str = '; '.join([f"{v.date_of_care}: {v.veterinary_care.care_name}" for v in vet_history])
                
                row_data.extend([mother, father, children_str, weight_str or 'Нет данных', vet_str or 'Нет данных'])
            
            export_data.append(row_data)
        
        # Создаем файл в зависимости от доступности openpyxl
        if use_excel:
            # Создаём Excel файл
            wb = Workbook()
            ws = wb.active
            ws.title = f"{animal_type.capitalize()}s"
            
            # Стилизация заголовков
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            
            # Добавляем заголовки
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num, value=header)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
            
            # Добавляем данные
            for row_num, row_data in enumerate(export_data, start=2):
                for col_num, value in enumerate(row_data, 1):
                    ws.cell(row=row_num, column=col_num, value=value)
            
            # Автоширина колонок
            for col in range(1, len(headers) + 1):
                ws.column_dimensions[get_column_letter(col)].width = 15
            
            # Сохраняем в response
            filename = f"{animal_type}s_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
            
            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            wb.save(response)
        else:
            # Создаём CSV файл
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Добавляем заголовки
            writer.writerow(headers)
            
            # Добавляем данные
            for row_data in export_data:
                writer.writerow(row_data)
            
            # Сохраняем в response
            filename = f"{animal_type}s_{datetime.now().strftime('%Y-%m-%d')}.csv"
            
            response = HttpResponse(
                output.getvalue(),
                content_type='text/csv; charset=utf-8'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Ошибка экспорта: {error_details}")  # Для логов сервера
        return Response(
            {"error": f"Ошибка при создании Excel файла: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# API для статистики на главной странице

@api_view(['GET'])
def dashboard_statistics(request):
    """
    Возвращает статистику для главной страницы:
    - Всего активных животных (по типам)
    - Перенесено в архив за последний месяц (по типам и статусам)
    - Родилось за последний месяц (только молодняк Ram и Ewe, по типам)
    """
    from django.utils import timezone
    
    # Дата месяц назад
    one_month_ago = timezone.now().date() - timedelta(days=30)
    
    # 1. Всего активных животных
    active_makers = Maker.objects.filter(is_archived=False).count()
    active_rams = Ram.objects.filter(is_archived=False).count()
    active_ewes = Ewe.objects.filter(is_archived=False).count()
    active_sheep = Sheep.objects.filter(is_archived=False).count()
    total_active = active_makers + active_rams + active_ewes + active_sheep
    
    # 2. Перенесено в архив за последний месяц
    archive_statuses = ['Убыл', 'Убой', 'Продажа']
    
    archived_makers = Maker.objects.filter(
        is_archived=True,
        animal_status__status_type__in=archive_statuses,
        animal_status__date_of_status__gte=one_month_ago
    ).values('animal_status__status_type').annotate(count=Count('id'))
    
    archived_rams = Ram.objects.filter(
        is_archived=True,
        animal_status__status_type__in=archive_statuses,
        animal_status__date_of_status__gte=one_month_ago
    ).values('animal_status__status_type').annotate(count=Count('id'))
    
    archived_ewes = Ewe.objects.filter(
        is_archived=True,
        animal_status__status_type__in=archive_statuses,
        animal_status__date_of_status__gte=one_month_ago
    ).values('animal_status__status_type').annotate(count=Count('id'))
    
    archived_sheep = Sheep.objects.filter(
        is_archived=True,
        animal_status__status_type__in=archive_statuses,
        animal_status__date_of_status__gte=one_month_ago
    ).values('animal_status__status_type').annotate(count=Count('id'))
    
    # Подсчёт общего количества архивированных
    total_archived_makers = sum(item['count'] for item in archived_makers)
    total_archived_rams = sum(item['count'] for item in archived_rams)
    total_archived_ewes = sum(item['count'] for item in archived_ewes)
    total_archived_sheep = sum(item['count'] for item in archived_sheep)
    total_archived = total_archived_makers + total_archived_rams + total_archived_ewes + total_archived_sheep
    
    # 3. Родилось за последний месяц (только молодняк)
    born_rams = Ram.objects.filter(birth_date__gte=one_month_ago).count()
    born_ewes = Ewe.objects.filter(birth_date__gte=one_month_ago).count()
    total_born = born_rams + born_ewes
    
    return Response({
        'active_animals': {
            'total': total_active,
            'by_type': {
                'makers': active_makers,
                'rams': active_rams,
                'ewes': active_ewes,
                'sheep': active_sheep
            }
        },
        'archived_last_month': {
            'total': total_archived,
            'by_type': {
                'makers': {
                    'total': total_archived_makers,
                    'by_status': list(archived_makers)
                },
                'rams': {
                    'total': total_archived_rams,
                    'by_status': list(archived_rams)
                },
                'ewes': {
                    'total': total_archived_ewes,
                    'by_status': list(archived_ewes)
                },
                'sheep': {
                    'total': total_archived_sheep,
                    'by_status': list(archived_sheep)
                }
            }
        },
        'born_last_month': {
            'total': total_born,
            'by_type': {
                'rams': born_rams,
                'ewes': born_ewes
            }
        }
    })


@api_view(['GET'])
def yearly_statistics(request):
    """
    Возвращает статистику за выбранный год:
    - Средний набор веса по месяцам
    - Количество вакцинаций по препаратам
    - Количество животных по статусам на конец года
    - Количество рождений мальчиков и девочек
    """
    from django.utils import timezone
    from datetime import date
    from django.db.models import Avg, Count, F, Q
    from begunici.app_types.veterinary.vet_models import VeterinaryCare, Place
    
    year = request.GET.get('year', timezone.now().year)
    try:
        year = int(year)
    except (ValueError, TypeError):
        return Response({'error': 'Неверный формат года'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Даты начала и конца года
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        
        # 1. ОПТИМИЗИРОВАННЫЙ расчет среднего набора веса по месяцам
        monthly_weight_gain = {}
        
        # Получаем все взвешивания за год одним запросом
        all_weights = WeightRecord.objects.filter(
            weight_date__gte=year_start,
            weight_date__lte=year_end
        ).select_related('tag').order_by('tag', 'weight_date')
        
        # Группируем по месяцам и тегам
        from collections import defaultdict
        weights_by_month_tag = defaultdict(list)
        
        for weight in all_weights:
            month = weight.weight_date.month
            tag_id = weight.tag.id
            weights_by_month_tag[(month, tag_id)].append(weight)
        
        # Рассчитываем прирост по месяцам
        for month in range(1, 13):
            total_weight_gain = 0
            animals_with_gain = 0
            
            for (m, tag_id), weights in weights_by_month_tag.items():
                if m == month and len(weights) >= 2:
                    first_weight = weights[0].weight
                    last_weight = weights[-1].weight
                    weight_gain = float(last_weight - first_weight)
                    total_weight_gain += weight_gain
                    animals_with_gain += 1
            
            avg_gain = round(total_weight_gain / animals_with_gain, 2) if animals_with_gain > 0 else 0
            monthly_weight_gain[f'month_{month}'] = {
                'month': month,
                'avg_gain': avg_gain,
                'animals_count': animals_with_gain
            }
        
        # 2. ОПТИМИЗИРОВАННЫЙ подсчет вакцинаций
        treatment_stats = {}
        vet_treatments = Veterinary.objects.filter(
            date_of_care__gte=year_start,
            date_of_care__lte=year_end
        ).select_related('veterinary_care').values(
            'veterinary_care__care_name',
            'veterinary_care__medication'
        ).annotate(count=Count('id'))
        
        for treatment in vet_treatments:
            care_name = treatment['veterinary_care__care_name'] or 'Без названия'
            medication = treatment['veterinary_care__medication'] or 'Без препарата'
            key = f"{care_name} ({medication})"
            treatment_stats[key] = treatment['count']
        
        # 3. ОПТИМИЗИРОВАННЫЙ подсчет животных по статусам
        status_stats = {}
        
        # Используем агрегацию для подсчета животных по статусам
        for model in [Maker, Ram, Ewe, Sheep]:
            model_stats = model.objects.filter(
                tag__issue_date__lte=year_end
            ).values(
                'animal_status__status_type'
            ).annotate(count=Count('id'))
            
            for stat in model_stats:
                status_type = stat['animal_status__status_type']
                if status_type:
                    if status_type not in status_stats:
                        status_stats[status_type] = 0
                    status_stats[status_type] += stat['count']
        
        # 4. ОПТИМИЗИРОВАННЫЙ подсчет рождений
        # Используем агрегацию вместо count()
        boys_born = (
            Ram.objects.filter(birth_date__gte=year_start, birth_date__lte=year_end).count() +
            Maker.objects.filter(birth_date__gte=year_start, birth_date__lte=year_end).count()
        )
        
        girls_born = (
            Ewe.objects.filter(birth_date__gte=year_start, birth_date__lte=year_end).count() +
            Sheep.objects.filter(birth_date__gte=year_start, birth_date__lte=year_end).count()
        )
        
        return Response({
            'year': year,
            'monthly_weight_gain': monthly_weight_gain,
            'veterinary_treatments': treatment_stats,
            'animals_by_status': status_stats,
            'births': {
                'boys': boys_born,
                'girls': girls_born,
                'total': boys_born + girls_born
            }
        })
        
    except Exception as e:
        import traceback
        print(f"Ошибка в yearly_statistics: {str(e)}")
        print(traceback.format_exc())
        return Response({
            'error': f'Ошибка при получении статистики: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        avg_gain = round(total_weight_gain / animals_with_gain, 2) if animals_with_gain > 0 else 0
        monthly_weight_gain[f'month_{month}'] = {
            'month': month,
            'avg_gain': avg_gain,
            'animals_count': animals_with_gain
        }
    
    # 2. Количество вакцинаций по препаратам
    vet_treatments = Veterinary.objects.filter(
        date_of_care__gte=year_start,
        date_of_care__lte=year_end
    ).select_related('veterinary_care')
    
    treatment_stats = {}
    for treatment in vet_treatments:
        if treatment.veterinary_care:
            care_name = treatment.veterinary_care.care_name
            medication = treatment.veterinary_care.medication or 'Без препарата'
            key = f"{care_name} ({medication})"
            
            if key not in treatment_stats:
                treatment_stats[key] = 0
            treatment_stats[key] += 1
    
    # 3. Количество животных по статусам на конец года
    status_stats = {}
    
    # Получаем все статусы
    all_statuses = Status.objects.all()
    
    for status_obj in all_statuses:
        count = 0
        # Считаем животных каждого типа с этим статусом на конец года
        for model in [Maker, Ram, Ewe, Sheep]:
            count += model.objects.filter(
                animal_status=status_obj,
                # Животное должно существовать на конец года
                tag__issue_date__lte=year_end
            ).count()
        
        if count > 0:
            status_stats[status_obj.status_type] = count
    
    # 4. Рождения мальчиков и девочек за год
    # Мальчики: Ram + Maker
    boys_born = (
        Ram.objects.filter(birth_date__gte=year_start, birth_date__lte=year_end).count() +
        Maker.objects.filter(birth_date__gte=year_start, birth_date__lte=year_end).count()
    )
    
    # Девочки: Ewe
    girls_born = Ewe.objects.filter(birth_date__gte=year_start, birth_date__lte=year_end).count()
    
    # Sheep могут быть как мальчиками, так и девочками, но по логике это взрослые самки
    # Поэтому добавляем их к девочкам, если они родились в этом году
    girls_born += Sheep.objects.filter(birth_date__gte=year_start, birth_date__lte=year_end).count()
    
    return Response({
        'year': year,
        'monthly_weight_gain': monthly_weight_gain,
        'veterinary_treatments': treatment_stats,
        'animals_by_status': status_stats,
        'births': {
            'boys': boys_born,
            'girls': girls_born,
            'total': boys_born + girls_born
        }
    })


@api_view(['GET'])
def get_all_tags(request):
    """
    Возвращает список всех бирок с информацией о животных
    """
    try:
        search = request.GET.get('search', '')
        
        # Получаем все бирки
        tags_query = Tag.objects.all()
        
        if search:
            tags_query = tags_query.filter(tag_number__icontains=search)
        
        tags_data = []
        
        # Сначала добавляем активных животных
        for model, type_name in [(Maker, 'Производитель'), (Ram, 'Баран'), (Ewe, 'Ярка'), (Sheep, 'Овца')]:
            animals = model.objects.filter(is_archived=False, tag__in=tags_query).select_related('tag')
            for animal in animals:
                tags_data.append({
                    'tag_number': animal.tag.tag_number,
                    'animal_type': type_name,
                    'is_active': True,
                    'display_name': f'{type_name} {animal.tag.tag_number}'
                })
        
        # Затем добавляем архивных животных
        for model, type_name in [(Maker, 'Производитель'), (Ram, 'Баран'), (Ewe, 'Ярка'), (Sheep, 'Овца')]:
            animals = model.objects.filter(is_archived=True, tag__in=tags_query).select_related('tag')
            for animal in animals:
                tags_data.append({
                    'tag_number': animal.tag.tag_number,
                    'animal_type': type_name,
                    'is_active': False,
                    'display_name': f'{type_name} {animal.tag.tag_number} (архив)'
                })
        
        # Сортируем: сначала активные, потом по номеру бирки
        tags_data.sort(key=lambda x: (not x['is_active'], x['tag_number']))
        
        return Response(tags_data[:100])  # Ограничиваем до 100 результатов
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_all_statuses(request):
    """
    Возвращает список всех статусов с их цветами
    """
    try:
        statuses = Status.objects.all()
        statuses_data = []
        
        for status_obj in statuses:
            statuses_data.append({
                'id': status_obj.id,
                'status_type': status_obj.status_type,
                'color': status_obj.color
            })
        
        return Response(statuses_data)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# API для работы с бэкапами
@api_view(['POST'])
def create_backup(request):
    """
    Создает ручной бэкап базы данных
    """
    try:
        success, message = backup_manager.create_manual_backup()
        
        if success:
            return Response({
                'success': True,
                'message': message
            })
        else:
            return Response({
                'success': False,
                'error': message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def backup_info(request):
    """
    Возвращает информацию о последнем бэкапе
    """
    try:
        last_backup = backup_manager.get_last_backup_info()
        
        return Response({
            'last_backup': last_backup
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def check_auto_backup(request):
    """
    Проверяет и создает автобэкап если нужно
    """
    try:
        if backup_manager.should_create_auto_backup():
            success, message = backup_manager.create_auto_backup()
            return Response({
                'created': success,
                'message': message
            })
        else:
            return Response({
                'created': False,
                'message': 'Автобэкап не требуется'
            })
            
    except Exception as e:
        return Response({
            'created': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)