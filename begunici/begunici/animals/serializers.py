from rest_framework import serializers
from .models import Maker, Ram, Ewe, Sheep, Lamb
from veterinary.serializers import StatusSerializer, TagSerializer, VeterinaryCareSerializer, WeightRecordSerializer, PlaceSerializer


# Сериализатор для ягнят
class LambSerializer(serializers.ModelSerializer):
    tag = TagSerializer(read_only=True)

    class Meta:
        model = Lamb
        fields = '__all__'

# Сериализатор для баранов
class RamSerializer(serializers.ModelSerializer):
    tag = TagSerializer(read_only=True)
    status = StatusSerializer(read_only=True)
    place = PlaceSerializer(read_only=True)
    veterinary_care = VeterinaryCareSerializer(read_only=True)
    weight_records = WeightRecordSerializer(read_only=True)

    class Meta:
        model = Ram
        fields = '__all__'

# Сериализатор для ярок (Ewe)
class EweSerializer(serializers.ModelSerializer):
    tag = TagSerializer(read_only=True)
    status = StatusSerializer(read_only=True)
    place = PlaceSerializer(read_only=True)
    veterinary_care = VeterinaryCareSerializer(read_only=True)
    weight_records = WeightRecordSerializer(read_only=True)

    class Meta:
        model = Ewe
        fields = '__all__'

# Сериализатор для овец (Sheep)
class SheepSerializer(serializers.ModelSerializer):
    tag = TagSerializer(read_only=True)
    status = StatusSerializer(read_only=True)
    place = PlaceSerializer(read_only=True)
    veterinary_care = VeterinaryCareSerializer(read_only=True)
    weight_records = WeightRecordSerializer(read_only=True)

    class Meta:
        model = Sheep
        fields = '__all__'

# Сериализатор для производителей (Maker)
class MakerSerializer(serializers.ModelSerializer):
    tag = TagSerializer(read_only=True)
    status = StatusSerializer(read_only=True)
    place = PlaceSerializer(read_only=True)
    veterinary_care = VeterinaryCareSerializer(read_only=True)
    weight_records = WeightRecordSerializer(read_only=True)

    class Meta:
        model = Maker
        fields = '__all__'
