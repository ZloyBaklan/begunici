from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator
from .models import Maker, Ram, Ewe, Sheep, Lamb
from .serializers import MakerSerializer, RamSerializer, EweSerializer, SheepSerializer, LambSerializer
from veterinary.models import Tag, Status, Place



# 1. Вывод всех объектов постранично
@api_view(['GET'])
def list_objects(request, model, serializer_class, per_page=10):
    objects = model.objects.all()
    paginator = Paginator(objects, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    serializer = serializer_class(page_obj, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def maker_list(request):
    return list_objects(request, Maker, MakerSerializer)

@api_view(['GET'])
def ram_list(request):
    return list_objects(request, Ram, RamSerializer)

@api_view(['GET'])
def ewe_list(request):
    return list_objects(request, Ewe, EweSerializer)

@api_view(['GET'])
def sheep_list(request):
    return list_objects(request, Sheep, SheepSerializer)

@api_view(['GET'])
def lamb_list(request):
    return list_objects(request, Lamb, LambSerializer)

# 2. Создание новых записей
@api_view(['POST'])
def create_object(request, serializer_class, model):
    serializer = serializer_class(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def create_maker(request):
    return create_object(request, MakerSerializer, Maker)

@api_view(['POST'])
def create_ram(request):
    return create_object(request, RamSerializer, Ram)

@api_view(['POST'])
def create_ewe(request):
    return create_object(request, EweSerializer, Ewe)

@api_view(['POST'])
def create_sheep(request):
    return create_object(request, SheepSerializer, Sheep)

@api_view(['POST'])
def create_lamb(request):
    return create_object(request, LambSerializer, Lamb)

# 3. Преобразование Ewe в Sheep
@api_view(['POST'])
def ewe_to_sheep(request, ewe_id):
    try:
        ewe = Ewe.objects.get(id=ewe_id)
        if ewe.status.status_type == 'Случка':
            sheep_data = {
                'tag': ewe.tag.id,
                'status': ewe.status.id,
                'birth_date': ewe.birth_date,
                'age': ewe.age,
                'mother_tag': ewe.mother_tag,
                'father_tag': ewe.father_tag,
                'place': ewe.place.id,
                'replace_date': ewe.replace_date,
                'last_weight': ewe.last_weight,
                'last_weight_date': ewe.last_weight_date,
                'weight_records': ewe.weight_records.id,
                'veterinary_care': ewe.veterinary_care.id,
            }
            sheep_serializer = SheepSerializer(data=sheep_data)
            if sheep_serializer.is_valid():
                sheep_serializer.save()
                ewe.delete()  # Удаляем Ewe
                return Response(sheep_serializer.data, status=status.HTTP_201_CREATED)
            return Response(sheep_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "Ewe is not ready for conversion"}, status=status.HTTP_400_BAD_REQUEST)
    except Ewe.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

# 4. Перенос ягненка в Ram или Ewe
@api_view(['POST'])
def lamb_to_ram_or_ewe(request, lamb_id):
    try:
        lamb = Lamb.objects.get(id=lamb_id)
        if lamb.gender == 'М':
            ram_data = {
                'tag': lamb.tag.id,
                'birth_date': lamb.birth_date,
                'age': 0,
                'mother_tag': lamb.tag.tag_number,
                'father_tag': 'UNKNOWN',  # Указать отца
                'place': lamb.place.id,
                'last_weight': lamb.weight,
                'last_weight_date': lamb.birth_date,
                'status': Status.objects.get(status_type='Новорожденный').id
            }
            ram_serializer = RamSerializer(data=ram_data)
            if ram_serializer.is_valid():
                ram_serializer.save()
                lamb.delete()  # Удаляем запись Lamb
                return Response(ram_serializer.data, status=status.HTTP_201_CREATED)
            return Response(ram_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        elif lamb.gender == 'Ж':
            ewe_data = {
                'tag': lamb.tag.id,
                'birth_date': lamb.birth_date,
                'age': 0,
                'mother_tag': lamb.tag.tag_number,
                'father_tag': 'UNKNOWN',
                'place': lamb.place.id,
                'last_weight': lamb.weight,
                'last_weight_date': lamb.birth_date,
                'status': Status.objects.get(status_type='Новорожденный').id
            }
            ewe_serializer = EweSerializer(data=ewe_data)
            if ewe_serializer.is_valid():
                ewe_serializer.save()
                lamb.delete()  # Удаляем запись Lamb
                return Response(ewe_serializer.data, status=status.HTTP_201_CREATED)
            return Response(ewe_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Lamb.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

