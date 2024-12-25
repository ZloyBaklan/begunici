from rest_framework import serializers
from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase
from begunici.app_types.veterinary.vet_models import Place, Tag, Status, Veterinary, WeightRecord
from begunici.app_types.veterinary.vet_serializers import StatusSerializer, PlaceSerializer, WeightRecordSerializer, VeterinarySerializer, TagSerializer


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
    mother = TagSerializer(read_only=True)  # Для отображения полной информации о матери
    mother_id = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), write_only=True, source='mother', allow_null=True, required=False
    )  # Для указания идентификатора матери

    father = TagSerializer(read_only=True)  # Для отображения полной информации об отце
    father_id = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), write_only=True, source='father', allow_null=True, required=False
    )  # Для указания идентификатора отца
    children = serializers.SerializerMethodField()

    class Meta:
        model = AnimalBase
        fields = '__all__'
    
    def create(self, validated_data):
        # Создание или привязка бирки
        tag_number = validated_data.pop('tag', None)
        if tag_number:
            tag, created = Tag.objects.get_or_create(tag_number=tag_number)
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

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.tag:
            representation['tag'] = {
                'id': instance.tag.id,
                'tag_number': instance.tag.tag_number
            }
        else:
            representation['tag'] = None
        return representation


class MakerSerializer(AnimalBaseSerializer):
    plemstatus = serializers.CharField(max_length=200)
    working_condition = serializers.CharField(max_length=200)
    

    class Meta(AnimalBaseSerializer.Meta):
        model = Maker
        fields = '__all__'
    
    def get_children(self, obj):
        # Используем метод get_children из модели Maker
        children = obj.get_children()
        return MakerSerializer(children, many=True).data

    

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



class LambingSerializer(serializers.ModelSerializer):
    ewe = serializers.PrimaryKeyRelatedField(queryset=Ewe.objects.all())
    maker = serializers.PrimaryKeyRelatedField(queryset=Maker.objects.all())

    class Meta:
        model = Lambing
        fields = '__all__'
