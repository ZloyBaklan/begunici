from rest_framework import serializers
from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase
from begunici.app_types.veterinary.serializers import TagSerializer, StatusSerializer, PlaceSerializer, WeightRecordSerializer, VeterinarySerializer


class AnimalSerializer(serializers.ModelSerializer):
    tag = serializers.StringRelatedField()  # Отображаем бирку как строку
    
    class Meta:
        model = AnimalBase
        fields = '__all__'


# Сериализатор для производитель (Maker)
class MakerSerializer(serializers.ModelSerializer):
    tag = TagSerializer()  # Вложенный сериализатор для бирки
    animal_status = StatusSerializer()  # Вложенный сериализатор для статуса
    weight_records = WeightRecordSerializer(many=True, required=False)  # История взвешиваний
    veterinary_history = VeterinarySerializer(many=True, required=False)  # История ветобработок
    place = PlaceSerializer()  # Вложенный сериализатор для места

    class Meta:
        model = Maker
        fields = '__all__'

    def create(self, validated_data):
        # Логика создания производителя
        return Maker.objects.create(**validated_data)

    def update(self, instance, validated_data):
        # Логика обновления данных производителя
        instance.working_condition = validated_data.get('working_condition', instance.working_condition)
        instance.plemstatus = validated_data.get('plemstatus', instance.plemstatus)
        instance.save()
        return instance

# Сериализатор для барана (Ram)
class RamSerializer(serializers.ModelSerializer):
    tag = TagSerializer()  # Вложенный сериализатор для бирки
    animal_status = StatusSerializer()  # Вложенный сериализатор для статуса
    weight_records = WeightRecordSerializer(many=True, required=False)  # История взвешиваний
    veterinary_history = VeterinarySerializer(many=True, required=False)  # История ветобработок
    place = PlaceSerializer()  # Вложенный сериализатор для места

    class Meta:
        model = Ram
        fields = '__all__'

    def create(self, validated_data):
        return Ram.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.mother_tag = validated_data.get('mother_tag', instance.mother_tag)
        instance.father_tag = validated_data.get('father_tag', instance.father_tag)
        instance.save()
        return instance

# Сериализатор для ярки (Ewe)
class EweSerializer(serializers.ModelSerializer):
    tag = TagSerializer()  # Вложенный сериализатор для бирки
    animal_status = StatusSerializer()  # Вложенный сериализатор для статуса
    weight_records = WeightRecordSerializer(many=True, required=False)  # История взвешиваний
    veterinary_history = VeterinarySerializer(many=True, required=False)  # История ветобработок
    place = PlaceSerializer()  # Вложенный сериализатор для места

    class Meta:
        model = Ewe
        fields = '__all__'

    def create(self, validated_data):
        return Ewe.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.mother_tag = validated_data.get('mother_tag', instance.mother_tag)
        instance.father_tag = validated_data.get('father_tag', instance.father_tag)
        instance.save()
        return instance

# Сериализатор для овцы (Sheep)
class SheepSerializer(serializers.ModelSerializer):
    tag = TagSerializer()  # Вложенный сериализатор для бирки
    animal_status = StatusSerializer()  # Вложенный сериализатор для статуса
    weight_records = WeightRecordSerializer(many=True, required=False)  # История взвешиваний
    veterinary_history = VeterinarySerializer(many=True, required=False)  # История ветобработок
    place = PlaceSerializer()  # Вложенный сериализатор для места
    lambing_history = serializers.SerializerMethodField()  # История окотов

    class Meta:
        model = Sheep
        fields = '__all__'

    def get_lambing_history(self, obj):
        lambings = Lambing.objects.filter(ewe=obj)  # Получаем все окоты для овцы
        return LambingSerializer(lambings, many=True).data

    def create(self, validated_data):
        return Sheep.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.animal_status = validated_data.get('animal_status', instance.animal_status)
        instance.place = validated_data.get('place', instance.place)
        instance.save()
        return instance

# Сериализатор для окота (Lambing)
class LambingSerializer(serializers.ModelSerializer):
    ewe = EweSerializer()  # Вложенный сериализатор для ярки
    maker = MakerSerializer()  # Вложенный сериализатор для производителя
    lambs_data = serializers.JSONField()  # Поле для хранения информации о потомстве

    class Meta:
        model = Lambing
        fields = '__all__'

    def create(self, validated_data):
        return Lambing.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.ewe = validated_data.get('ewe', instance.ewe)
        instance.maker = validated_data.get('maker', instance.maker)
        instance.actual_lambing_date = validated_data.get('actual_lambing_date', instance.actual_lambing_date)
        instance.lambs_data = validated_data.get('lambs_data', instance.lambs_data)
        instance.save()
        return instance
