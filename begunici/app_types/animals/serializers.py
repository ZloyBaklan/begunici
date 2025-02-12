from rest_framework import serializers
from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase
from begunici.app_types.veterinary.vet_models import Place, PlaceMovement, Tag, Status, Veterinary, WeightRecord, StatusHistory
from begunici.app_types.veterinary.vet_serializers import StatusSerializer, PlaceSerializer, WeightRecordSerializer, VeterinarySerializer, TagSerializer, PlaceMovementSerializer, StatusHistorySerializer


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    Сериализатор с динамическими полями. Позволяет включать/исключать поля через запросы.
    """
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        super().__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)

class AnimalBaseSerializer(DynamicFieldsModelSerializer):
    animal_status = StatusSerializer(read_only=True)  # Для чтения используется StatusSerializer
    animal_status_id = serializers.PrimaryKeyRelatedField(
        queryset=Status.objects.all(), write_only=True, source='animal_status'
    )  # Для записи используется PrimaryKeyRelatedField
    tag = serializers.CharField()  # Бирка как строка (для создания/редактирования)
    #tag_number = serializers.CharField(source='tag.tag_number', write_only=True)  # Для ввода номера бирки
    weight_records = serializers.SerializerMethodField()
    veterinary_history = serializers.SerializerMethodField()
    place = PlaceSerializer(read_only=True)  # Для чтения полного объекта
    place_id = serializers.PrimaryKeyRelatedField(
        queryset=Place.objects.all(), write_only=True, source='place'
    )  # Для записи идентификатора места
    is_archived = serializers.BooleanField(read_only=True)
    archived_date = serializers.SerializerMethodField()  # Новое поле для даты архивирования
    mother = TagSerializer(read_only=True)  # Для отображения полной информации о матери
    mother_id = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), write_only=True, source='mother', allow_null=True, required=False
    )  # Для указания идентификатора матери

    father = TagSerializer(read_only=True)  # Для отображения полной информации об отце
    father_id = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), write_only=True, source='father', allow_null=True, required=False
    )  # Для указания идентификатора отца
    children = serializers.SerializerMethodField()
    place_movements = PlaceMovementSerializer(many=True, read_only=True)
    status_history = StatusHistorySerializer(many=True, read_only=True)
    

    class Meta:
        model = AnimalBase
        fields = '__all__'
    
    def create(self, validated_data):
        # Создание или привязка бирки
        tag_number = validated_data.pop('tag', None)
        if tag_number:
            tag, created = Tag.objects.get_or_create(tag_number=tag_number)
            # Устанавливаем animal_type в зависимости от типа животного
            if isinstance(self.Meta.model, Maker):
                tag.animal_type = "Maker"
            elif isinstance(self.Meta.model, Sheep):
                tag.animal_type = "Sheep"
            elif isinstance(self.Meta.model, Ewe):
                tag.animal_type = "Ewe"
            elif isinstance(self.Meta.model, Ram):
                tag.animal_type = "Ram"
            tag.save()
            validated_data['tag'] = tag

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Обновление бирки
        tag_number = validated_data.pop('tag', None)
        if tag_number and instance.tag.tag_number != tag_number:
            instance.tag.update_tag(tag_number)
        return super().update(instance, validated_data)

    
    def get_weight_records(self, obj):
        # Получаем записи веса через тег
        weight_records = WeightRecord.objects.filter(tag=obj.tag).order_by('-weight_date')
        return WeightRecordSerializer(weight_records, many=True).data

    def get_veterinary_history(self, obj):
        # Получаем записи ветобработок через тег
        vet_history = Veterinary.objects.filter(tag=obj.tag).select_related('veterinary_care').order_by('-date_of_care')
        return VeterinarySerializer(vet_history, many=True).data

    def get_archived_date(self, obj):
        """
        Возвращаем дату архивирования на основе даты статуса.
        """
        if obj.is_archived and obj.animal_status:
            return obj.animal_status.date_of_status
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.tag:
            representation['tag'] = {
                'id': instance.tag.id,
                'tag_number': instance.tag.tag_number,
                'animal_type': instance.tag.animal_type  # Добавляем animal_type
            }
        else:
            representation['tag'] = None
        
        # Добавляем дату архивирования в представление
        representation['archived_date'] = self.get_archived_date(instance)
        return representation


class MakerSerializer(AnimalBaseSerializer):
    plemstatus = serializers.CharField(max_length=200)
    working_condition = serializers.CharField(max_length=200)
    working_condition_date = serializers.DateField(required=False, allow_null=True)  # Добавляем поле даты
    
    
    class Meta(AnimalBaseSerializer.Meta):
        model = Maker
        fields = '__all__'
    
    def get_children(self, obj):
        children = obj.get_children()
        return MakerChildSerializer(children, many=True).data
    
    def get_place_history(self, obj):
        place_movements = PlaceMovement.objects.filter(tag=obj.tag).order_by('-new_place__date_of_transfer')
        return [
            {
                'old_place': movement.old_place,
                'new_place': movement.new_place,
                'date_of_transfer': movement.new_place.date_of_transfer,
            }
            for movement in place_movements
        ]
    def get_status_history(self, obj):
        status_history = StatusHistory.objects.filter(tag=obj.tag).order_by('-new_status__date_of_status')
        return [
            {
                'old_status': status_i.old_status,
                'new_status': status_i.new_status,
                'date_of_status': status_i.new_status.date_of_status,
            }
            for status_i in status_history
        ]

            

class MakerChildSerializer(serializers.ModelSerializer):
    link = serializers.SerializerMethodField()
    tag_number = serializers.CharField(source='tag.tag_number', read_only=True)
    animal_type = serializers.CharField(source='tag.animal_type', read_only=True)
    is_archived = serializers.BooleanField(read_only=True)
    archive_status = serializers.CharField(source='animal_status.status_type', read_only=True)  # Статус
    archive_date = serializers.DateField(source='animal_status.date_of_status', read_only=True)  # Дата статуса

    class Meta:
        model = Maker
        fields = ['id', 'tag_number', 'animal_type', 'age', 'link', 'is_archived', 'archive_status', 'archive_date']


    def get_link(self, obj):
        animal_type_to_route = {
            'Maker': 'maker',
            'Sheep': 'sheep',
            'Ewe': 'ewe',
            'Ram': 'ram',
        }
        # Генерируем ссылку в зависимости от типа животного
        return f"/animals/{animal_type_to_route.get(obj.tag.animal_type, 'unknown')}/{obj.id}/info/"




class RamSerializer(AnimalBaseSerializer):
    class Meta(AnimalBaseSerializer.Meta):
        model = Ram
        fields = '__all__'

class EweSerializer(AnimalBaseSerializer):
    class Meta(AnimalBaseSerializer.Meta):
        model = Ewe
        fields = '__all__'


class SheepSerializer(AnimalBaseSerializer):
    lambing_history = serializers.SerializerMethodField()

    class Meta(AnimalBaseSerializer.Meta):
        model = Sheep
        fields = '__all__'

    def get_lambing_history(self, obj):
        lambings = Lambing.objects.filter(ewe=obj)
        return LambingSerializer(lambings, many=True).data
    
    def get_children(self, obj):
        # Используем метод get_children из модели Sheep
        children = obj.get_children()
        return SheepSerializer(children, many=True).data

class SheepChildSerializer(serializers.ModelSerializer):
    link = serializers.SerializerMethodField()

    class Meta:
        model = Sheep
        fields = ['id', 'tag', 'age', 'link']

    def get_link(self, obj):
        animal_type_to_route = {
            'Maker': 'maker',
            'Sheep': 'sheep',
            'Ewe': 'ewe',
            'Ram': 'ram',
        }
        # Генерируем ссылку в зависимости от типа животного
        return f"/animals/{animal_type_to_route.get(obj.tag.animal_type, 'unknown')}/{obj.id}/info/"


class LambingSerializer(serializers.ModelSerializer):
    ewe = serializers.PrimaryKeyRelatedField(queryset=Ewe.objects.all())
    maker = serializers.PrimaryKeyRelatedField(queryset=Maker.objects.all())

    class Meta:
        model = Lambing
        fields = '__all__'


class ArchiveAnimalSerializer(serializers.Serializer):
    """
    Полиморфный сериализатор для архива животных.
    """
    id = serializers.IntegerField()
    tag_number = serializers.CharField()
    animal_type = serializers.CharField()
    status = serializers.CharField(source='animal_status__status_type', allow_null=True)
    date_of_status = serializers.DateField(source='animal_status__date_of_status', allow_null=True)
    place = serializers.CharField(source='place__sheepfold', allow_null=True)
    birth_date = serializers.DateField()
    age = serializers.DecimalField(max_digits=5, decimal_places=1)

    def to_representation(self, instance):
        # Если instance — это словарь (после использования .values())
        if isinstance(instance, dict):
            return {
                'id': instance['id'],
                'tag_number': instance['tag__tag_number'],
                'animal_type': instance['tag__animal_type'],
                'status': instance.get('animal_status__status_type', 'Нет данных'),
                'archived_date': instance['animal_status__date_of_status'],
                'place': instance.get('place__sheepfold', 'Нет данных'),
                'birth_date': instance['birth_date'],
                'age': instance['age'],
            }
        # Если instance — это объект модели
        tag_number = instance.tag.tag_number if instance.tag else 'Нет данных'
        animal_type = instance.tag.animal_type if instance.tag else 'Unknown'
        return {
            'id': instance.id,
            'tag_number': tag_number,
            'animal_type': animal_type,
            'status': instance.animal_status.status_type if instance.animal_status else 'Нет данных',
            'archived_date': instance.animal_status.date_of_status if instance.animal_status else 'Нет данных',
            'place': instance.place.sheepfold if instance.place else 'Нет данных',
            'birth_date': instance.birth_date,
            'age': instance.age,
        }





