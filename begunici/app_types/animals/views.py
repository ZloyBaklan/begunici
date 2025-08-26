from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import Http404

from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase
from .serializers import (
    MakerSerializer,
    MakerChildSerializer,
    RamSerializer,
    EweSerializer,
    SheepSerializer,
    LambingSerializer,
    ArchiveAnimalSerializer,
)
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination

from begunici.app_types.veterinary.vet_models import (
    WeightRecord,
    Veterinary,
    PlaceMovement,
    Tag,
    StatusHistory,
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
        ).order_by("-new_status__date_of_status")

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
        maker.is_archived = False
        maker.save()
        return Response({"success": "Maker restored from archive"}, status=status.HTTP_200_OK)


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
        return Response(RamSerializer(children, many=True).data)

    @action(detail=True, methods=["get"], url_path="status_history")
    def status_history(self, request, pk=None):
        ram = self.get_object()
        status_history = StatusHistory.objects.filter(tag=ram.tag).order_by("-id")
        return Response(StatusHistorySerializer(status_history, many=True).data)

    @action(detail=True, methods=["get"], url_path="place_history")
    def place_history(self, request, pk=None):
        ram = self.get_object()
        place_movements = PlaceMovement.objects.filter(tag=ram.tag).order_by("-id")
        return Response(PlaceMovementSerializer(place_movements, many=True).data)

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        """Восстановление барана из архива"""
        ram = self.get_object()
        ram.is_archived = False
        ram.save()
        return Response({"success": "Ram restored from archive"}, status=status.HTTP_200_OK)


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

    @action(detail=True, methods=["post"])
    def to_sheep(self, request, pk=None, url_path="to_sheep"):
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
        return Response(EweSerializer(children, many=True).data)

    @action(detail=True, methods=["get"], url_path="status_history")
    def status_history(self, request, pk=None):
        ewe = self.get_object()
        status_history = StatusHistory.objects.filter(tag=ewe.tag).order_by("-id")
        return Response(StatusHistorySerializer(status_history, many=True).data)

    @action(detail=True, methods=["get"], url_path="place_history")
    def place_history(self, request, pk=None):
        ewe = self.get_object()
        place_movements = PlaceMovement.objects.filter(tag=ewe.tag).order_by("-id")
        return Response(PlaceMovementSerializer(place_movements, many=True).data)

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        """Восстановление ярки из архива"""
        ewe = self.get_object()
        ewe.is_archived = False
        ewe.save()
        return Response({"success": "Ewe restored from archive"}, status=status.HTTP_200_OK)


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
        return Response(SheepSerializer(children, many=True).data)

    @action(detail=True, methods=["get"], url_path="status_history")
    def status_history(self, request, pk=None):
        sheep = self.get_object()
        status_history = StatusHistory.objects.filter(tag=sheep.tag).order_by("-id")
        return Response(StatusHistorySerializer(status_history, many=True).data)

    @action(detail=True, methods=["get"], url_path="place_history")
    def place_history(self, request, pk=None):
        sheep = self.get_object()
        place_movements = PlaceMovement.objects.filter(tag=sheep.tag).order_by("-id")
        return Response(PlaceMovementSerializer(place_movements, many=True).data)

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        """Восстановление овцы из архива"""
        sheep = self.get_object()
        sheep.is_archived = False
        sheep.save()
        return Response({"success": "Sheep restored from archive"}, status=status.HTTP_200_OK)


class LambingViewSet(viewsets.ModelViewSet):
    queryset = Lambing.objects.all()
    serializer_class = LambingSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter]


class MakersView(TemplateView):
    template_name = "makers.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class MakerDetailView(TemplateView):
    template_name = "maker_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag_number = self.kwargs.get("tag_number")
        maker = Maker.objects.filter(tag__tag_number=tag_number).first()
        try:
            maker = Maker.objects.get(tag__tag_number=tag_number)
            context["maker"] = maker
        except Maker.DoesNotExist:
            print(
                f"Maker with tag_number={tag_number} not found"
            )  # Отладочная информация
            raise Http404("Производитель не найден")
        return context


class RamDetailView(TemplateView):
    template_name = "ram_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag_number = self.kwargs.get("tag_number")
        try:
            ram = Ram.objects.get(tag__tag_number=tag_number)
            context["ram"] = ram
        except Ram.DoesNotExist:
            print(f"Ram with tag_number={tag_number} not found")
            raise Http404("Баран не найден")
        return context


class EweDetailView(TemplateView):
    template_name = "ewe_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag_number = self.kwargs.get("tag_number")
        try:
            ewe = Ewe.objects.get(tag__tag_number=tag_number)
            context["ewe"] = ewe
        except Ewe.DoesNotExist:
            print(f"Ewe with tag_number={tag_number} not found")
            raise Http404("Ярка не найдена")
        return context


class SheepDetailView(TemplateView):
    template_name = "sheep_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag_number = self.kwargs.get("tag_number")
        try:
            sheep = Sheep.objects.get(tag__tag_number=tag_number)
            context["sheep"] = sheep
        except Sheep.DoesNotExist:
            print(f"Sheep with tag_number={tag_number} not found")
            raise Http404("Овца не найдена")
        return context


class MakerAnalyticsView(TemplateView):
    template_name = "maker_analytics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag_number = self.kwargs.get("tag_number")
        maker = Maker.objects.filter(tag__tag_number=tag_number).first()
        try:
            maker = Maker.objects.get(tag__tag_number=tag_number)
            context["maker"] = maker
        except Maker.DoesNotExist:
            raise Http404("Производитель не найден")
        # Используем метод сериализации детей
        serialized_maker = MakerSerializer(maker).data
        # Используем обновленный сериализатор для детей
        children = maker.get_children()  # Получаем детей через метод модели
        children_serialized = MakerChildSerializer(children, many=True).data
        context.update(
            {
                "maker": serialized_maker,
                "children": children_serialized,  # Дети уже сериализованы
                "status_history": StatusHistorySerializer(
                    StatusHistory.objects.filter(tag=maker.tag).order_by("-id"),
                    many=True,
                ).data,
                "place_movements": PlaceMovementSerializer(
                    PlaceMovement.objects.filter(tag=maker.tag).order_by(
                        "-new_place__date_of_transfer"
                    ),
                    many=True,
                ).data,
                "veterinary_history": VeterinarySerializer(
                    Veterinary.objects.filter(tag=maker.tag).order_by("-date_of_care"),
                    many=True,
                ).data,
                "weight_records": WeightRecordSerializer(
                    WeightRecord.objects.filter(tag=maker.tag).order_by("-weight_date"),
                    many=True,
                ).data,
            }
        )
        return context


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
        makers = Maker.objects.filter(is_archived=True).values(
            "id",
            "tag__tag_number",
            "tag__animal_type",
            "animal_status__status_type",
            "animal_status__date_of_status",
            "place__sheepfold",
            "birth_date",
            "age",
        )
        sheep = Sheep.objects.filter(is_archived=True).values(
            "id",
            "tag__tag_number",
            "tag__animal_type",
            "animal_status__status_type",
            "animal_status__date_of_status",
            "place__sheepfold",
            "birth_date",
            "age",
        )
        ewes = Ewe.objects.filter(is_archived=True).values(
            "id",
            "tag__tag_number",
            "tag__animal_type",
            "animal_status__status_type",
            "animal_status__date_of_status",
            "place__sheepfold",
            "birth_date",
            "age",
        )
        rams = Ram.objects.filter(is_archived=True).values(
            "id",
            "tag__tag_number",
            "tag__animal_type",
            "animal_status__status_type",
            "animal_status__date_of_status",
            "place__sheepfold",
            "birth_date",
            "age",
        )

        return makers.union(sheep, ewes, rams)


# Представления для страниц


def animals(request):
    return render(request, "animals.html")


def create_animal(request):
    return render(request, "create_animal.html")
