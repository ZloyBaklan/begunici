from rest_framework import serializers
from .models import Veterinary, Status, Tag, VeterinaryCare, WeightRecord, Place


# Сериализатор для статусов
class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = '__all__'

    def create(self, validated_data):
        # Логика создания статуса
        status = Status.objects.create(**validated_data)
        return status

    def update(self, instance, validated_data):
        # Логика обновления статуса
        instance.status_type = validated_data.get('status_type', instance.status_type)
        instance.save()
        return instance

# Сериализатор для места
class PlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Place
        fields = '__all__'

    def create(self, validated_data):
        # Логика создания места
        place = Place.objects.create(**validated_data)
        return place

    def update(self, instance, validated_data):
        # Логика обновления места
        instance.sheepfold = validated_data.get('sheepfold', instance.sheepfold)
        instance.compartment = validated_data.get('compartment', instance.compartment)
        instance.save()
        return instance

# Сериализатор для ветобработки
class VeterinaryCareSerializer(serializers.ModelSerializer):
    class Meta:
        model = VeterinaryCare
        fields = '__all__'

    def create(self, validated_data):
        # Логика создания ветобработки
        vet_care = VeterinaryCare.objects.create(**validated_data)
        return vet_care

    def update(self, instance, validated_data):
        # Логика обновления ветобработки
        instance.care_type = validated_data.get('care_type', instance.care_type)
        instance.save()
        return instance


# Сериализатор для бирки (Tag)
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'

# Сериализатор для взвешиваний
class WeightRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeightRecord
        fields = '__all__'





    
