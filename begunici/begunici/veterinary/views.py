from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator
from .models import Veterinary, Status, Tag, VeterinaryCare, WeightRecord, Lambing, Place, Sheep
from .serializers import (
    VeterinarySerializer, StatusSerializer, TagSerializer, VeterinaryCareSerializer,
    WeightRecordSerializer, LambingSerializer, PlaceSerializer
)
from animals.serializers import SheepSerializer

# Универсальная функция для создания новых объектов
@api_view(['POST'])
def create_object(request, serializer_class):
    serializer = serializer_class(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Универсальная функция для вывода списка объектов с постраничной навигацией
@api_view(['GET'])
def list_objects(request, model_class, serializer_class, per_page=10):
    objects = model_class.objects.all()
    paginator = Paginator(objects, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    serializer = serializer_class(page_obj, many=True)
    return Response(serializer.data)

# 1. Создание новых объектов
@api_view(['POST'])
def create_veterinary(request):
    return create_object(request, VeterinarySerializer)

@api_view(['POST'])
def create_status(request):
    return create_object(request, StatusSerializer)

@api_view(['POST'])
def create_tag(request):
    return create_object(request, TagSerializer)

@api_view(['POST'])
def create_veterinary_care(request):
    return create_object(request, VeterinaryCareSerializer)

@api_view(['POST'])
def create_weight_record(request):
    return create_object(request, WeightRecordSerializer)

@api_view(['POST'])
def create_lambing(request):
    return create_object(request, LambingSerializer)

@api_view(['POST'])
def create_place(request):
    return create_object(request, PlaceSerializer)

# 2. Вывод списков объектов
@api_view(['GET'])
def list_veterinary(request):
    return list_objects(request, Veterinary, VeterinarySerializer)

@api_view(['GET'])
def list_statuses(request):
    return list_objects(request, Status, StatusSerializer)

@api_view(['GET'])
def list_tags(request):
    return list_objects(request, Tag, TagSerializer)

@api_view(['GET'])
def list_veterinary_care(request):
    return list_objects(request, VeterinaryCare, VeterinaryCareSerializer)

@api_view(['GET'])
def list_weight_records(request):
    return list_objects(request, WeightRecord, WeightRecordSerializer)

@api_view(['GET'])
def list_lambing(request):
    return list_objects(request, Lambing, LambingSerializer)

@api_view(['GET'])
def list_places(request):
    return list_objects(request, Place, PlaceSerializer)

# 3. Функция для вывода всех окотов (Lambing) для конкретной овцы
@api_view(['GET'])
def sheep_lambings(request, sheep_id):
    try:
        sheep = Sheep.objects.get(id=sheep_id)
        lambings = Lambing.objects.filter(sheep=sheep)
        paginator = Paginator(lambings, 10)  # 10 записей на страницу
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        serializer = LambingSerializer(page_obj, many=True)
        return Response(serializer.data)
    except Sheep.DoesNotExist:
        return Response({"error": "Sheep not found"}, status=status.HTTP_404_NOT_FOUND)
