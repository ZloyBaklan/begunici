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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["date_of_status"]
    search_fields = ["status_type"]


class PlaceViewSet(viewsets.ModelViewSet):
    queryset = Place.objects.all()
    serializer_class = PlaceSerializer
    permission_classes = [AllowAny]
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
