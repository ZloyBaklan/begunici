from rest_framework import serializers
from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase
from begunici.app_types.veterinary.models import Place, Tag, Status
from begunici.app_types.veterinary.serializers import TagSerializer, StatusSerializer, PlaceSerializer, WeightRecordSerializer, VeterinarySerializer


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
    weight_records = WeightRecordSerializer(many=True, required=False)
    veterinary_history = VeterinarySerializer(many=True, required=False)
    place = PlaceSerializer(read_only=True)  # Для чтения полного объекта
    place_id = serializers.PrimaryKeyRelatedField(
        queryset=Place.objects.all(), write_only=True, source='place'
    )  # Для записи идентификатора места


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

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Добавляем поле sheepfold для отображения в клиенте
        representation['tag'] = {'id': instance.tag.id, 'tag_number': instance.tag.tag_number}
        return representation

class MakerSerializer(AnimalBaseSerializer):
    plemstatus = serializers.CharField(max_length=200)
    working_condition = serializers.CharField(max_length=200)
    

    class Meta(AnimalBaseSerializer.Meta):
        model = Maker
        fields = '__all__'

    

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



class LambingSerializer(serializers.ModelSerializer):
    ewe = serializers.PrimaryKeyRelatedField(queryset=Ewe.objects.all())
    maker = serializers.PrimaryKeyRelatedField(queryset=Maker.objects.all())

    class Meta:
        model = Lambing
        fields = '__all__'
