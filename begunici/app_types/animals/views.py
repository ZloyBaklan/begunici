from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator
from .models import Maker, Ram, Ewe, Sheep, Lamb, Lambing
from .serializers import MakerSerializer, RamSerializer, EweSerializer, SheepSerializer, LambSerializer, LambingSerializer
from begunici.app_types.veterinary.models import Status




# 1. Вывод всех объектов постранично
@api_view(['GET'])
def list_objects(request, model, serializer_class, per_page=10):
    objects = model.objects.all()
    paginator = Paginator(objects, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    serializer = serializer_class(page_obj, many=True)
    return Response(serializer.data)

# API для получения списка производителей
@api_view(['GET'])
def maker_list(request):
    makers = Maker.objects.all()
    serializer = MakerSerializer(makers, many=True)
    return Response(serializer.data)

# API для получения списка баранов
@api_view(['GET'])
def ram_list(request):
    rams = Ram.objects.all()
    serializer = RamSerializer(rams, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def ewe_list(request):
    return list_objects(request, Ewe, EweSerializer)

@api_view(['GET'])
def sheep_list(request):
    return list_objects(request, Sheep, SheepSerializer)

@api_view(['GET'])
def lamb_list(request):
    return list_objects(request, Lamb, LambSerializer)

@api_view(['GET'])
def list_lambing(request):
    return list_objects(request, Lambing, LambingSerializer)

# 2. Создание новых записей
@api_view(['POST'])
def create_object(request, serializer_class, model):
    serializer = serializer_class(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def create_lambing(request):
    return create_object(request, LambingSerializer)

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
        if ewe.animal_status.status_type == 'Случка':
            sheep_data = {
                'tag': ewe.tag.id,
                'status': ewe.animal_status.id,
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
        
        # Ищем запись окота (Lambing), связанную с овцой-матерью
        try:
            lambing = Lambing.objects.get(lambs__id=lamb_id)  # Ищем запись окота, связанного с ягнёнком
            mother_sheep = lambing.sheep  # Овца-мать из записи Lambing
            father_tag = lambing.maker.tag.tag_number  # Производитель (отец)
        except Lambing.DoesNotExist:
            return Response({"error": "Lambing record not found"}, status=status.HTTP_404_NOT_FOUND)

        # Проверяем пол ягнёнка и создаём запись либо для Ram, либо для Ewe
        if lamb.gender == 'М':
            ram_data = {
                'tag': lamb.tag.id,
                'birth_date': lamb.birth_date,
                'age': 0,
                'mother_tag': mother_sheep.tag.tag_number,  # Бирка овцы-матери
                'father_tag': father_tag,  # Бирка производителя (отца)
                'place': mother_sheep.place.id,  # Место, где находится овца-мать
                'last_weight': lamb.weight,
                'last_weight_date': lamb.birth_date,
                'animal_status': Status.objects.get(status_type='Новорожденный').id  # Статус "Новорожденный"
            }
            ram_serializer = RamSerializer(data=ram_data)
            if ram_serializer.is_valid():
                ram_serializer.save()
                lamb.delete()  # Удаляем запись Lamb после успешного переноса
                return Response(ram_serializer.data, status=status.HTTP_201_CREATED)
            return Response(ram_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        elif lamb.gender == 'Ж':
            ewe_data = {
                'tag': lamb.tag.id,
                'birth_date': lamb.birth_date,
                'age': 0,
                'mother_tag': mother_sheep.tag.tag_number,  # Бирка овцы-матери
                'father_tag': father_tag,  # Бирка производителя (отца)
                'place': mother_sheep.place.id,  # Место, где находится овца-мать
                'last_weight': lamb.weight,
                'last_weight_date': lamb.birth_date,
                'animal_status': Status.objects.get(status_type='Новорожденный').id  # Статус "Новорожденный"
            }
            ewe_serializer = EweSerializer(data=ewe_data)
            if ewe_serializer.is_valid():
                ewe_serializer.save()
                lamb.delete()  # Удаляем запись Lamb после успешного переноса
                return Response(ewe_serializer.data, status=status.HTTP_201_CREATED)
            return Response(ewe_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Lamb.DoesNotExist:
        return Response({"error": "Lamb not found"}, status=status.HTTP_404_NOT_FOUND)


# Универсальная функция для фильтрации по статусу, месту, возрасту и производителю
@api_view(['GET'])
def animal_filter(request, model_name):
    model = globals()[model_name]  # Получаем модель по имени
    serializer_class = globals()[model_name + 'Serializer']  # Получаем соответствующий сериализатор
    
    # Начальная фильтрация (без параметров — берем все записи)
    queryset = model.objects.all()

    # Фильтрация по animal_status (раньше было status)
    animal_status = request.GET.get('animal_status', None)
    if animal_status:
        queryset = queryset.filter(animal_status__status_type=animal_status)
    
    # Фильтрация по месту (с отсеком)
    place_id = request.GET.get('place', None)
    if place_id:
        queryset = queryset.filter(place__id=place_id)
    
    # Фильтрация по возрасту (диапазон)
    age_min = request.GET.get('age_min', None)
    age_max = request.GET.get('age_max', None)
    if age_min is not None and age_max is not None:
        age_min = int(age_min)
        age_max = int(age_max)
        queryset = queryset.filter(age__gte=age_min, age__lte=age_max)
    
    # Фильтрация по производителю (по отцу)
    father_tag = request.GET.get('father_tag', None)
    if father_tag:
        queryset = queryset.filter(father_tag=father_tag)
    
    # Пагинация
    paginator = Paginator(queryset, 10)  # 10 записей на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Сериализация и возврат данных
    serializer = serializer_class(page_obj, many=True)
    return Response(serializer.data)

# Отдельная функция для фильтрации овец по производителю (отец)
@api_view(['GET'])
def sheep_by_maker(request, maker_id):
    try:
        maker = Maker.objects.get(id=maker_id)
        sheep = Sheep.objects.filter(maker_tag=maker.tag.tag_number)  # Фильтрация по производителю (папе)
        paginator = Paginator(sheep, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        serializer = SheepSerializer(page_obj, many=True)
        return Response(serializer.data)
    except Maker.DoesNotExist:
        return Response({"error": "Maker not found"}, status=status.HTTP_404_NOT_FOUND)