from rest_framework import serializers
from .models import Veterinary, Status, Tag, VeterinaryCare, WeightRecord, Lambing, Place
from animals.serializers import LambSerializer


# Сериализатор для ветобработок
class VeterinarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Veterinary
        fields = '__all__'

# Сериализатор для Place (место овец)
class PlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Place
        fields = '__all__'

# Сериализатор для статусов
class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = '__all__'

# Сериализатор для бирки (Tag)
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'

# Сериализатор для типов ветобработок
class VeterinaryCareSerializer(serializers.ModelSerializer):
    class Meta:
        model = VeterinaryCare
        fields = '__all__'

# Сериализатор для взвешиваний
class WeightRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeightRecord
        fields = '__all__'


# Сериализатор для окота
class LambingSerializer(serializers.ModelSerializer):
    lambs = LambSerializer(many=True, read_only=True)
    
    class Meta:
        model = Lambing
        fields = '__all__'


    
