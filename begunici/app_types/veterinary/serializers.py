from rest_framework import serializers
from django.utils import timezone  # Не забудь импортировать timezone

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
        instance.color = validated_data.get('color', instance.color)  # Обновляем цвет
        # Проверяем, если дата вручную не указана, обновляем на текущую
        date_of_status = validated_data.get('date_of_status', None)
        if date_of_status is None:
            instance.date_of_status = timezone.now()  # Обновляем на текущую дату
        else:
            instance.date_of_status = date_of_status  # Устанавливаем вручную, если передана
        
        instance.save()
        return instance

# Сериализатор для места
class PlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Place
        fields = '__all__'

    def create(self, validated_data):
        # Логика создания места с возможностью установить дату перевода вручную
        return Place.objects.create(**validated_data)

    def update(self, instance, validated_data):
        # Логика обновления места
        instance.sheepfold = validated_data.get('sheepfold', instance.sheepfold)
        instance.compartment = validated_data.get('compartment', instance.compartment)
        
        # Проверяем, если дата перевода вручную не указана, обновляем на текущую
        date_of_transfer = validated_data.get('date_of_transfer', None)
        if date_of_transfer is None:
            instance.date_of_transfer = timezone.now()  # Обновляем на текущую дату
        else:
            instance.date_of_transfer = date_of_transfer  # Устанавливаем вручную, если передана
        
        instance.save()
        return instance


class VeterinaryCareSerializer(serializers.ModelSerializer):
    class Meta:
        model = VeterinaryCare
        fields = '__all__'

    def create(self, validated_data):
        """
        Создание новой записи ветобработки.
        """
        return VeterinaryCare.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Обновление существующего типа ветобработки.
        """
        instance.care_type = validated_data.get('care_type', instance.care_type)
        instance.care_name = validated_data.get('care_name', instance.care_name)
        instance.medication = validated_data.get('medication', instance.medication)
        instance.purpose = validated_data.get('purpose', instance.purpose)
        instance.save()
        return instance

class VeterinarySerializer(serializers.ModelSerializer):
    veterinary_care = VeterinaryCareSerializer()

    class Meta:
        model = Veterinary
        fields = '__all__'

    def create(self, validated_data):
        """
        Создание новой записи о ветобработке для животного.
        """
        veterinary_care_data = validated_data.pop('veterinary_care')
        veterinary_care = VeterinaryCare.objects.create(**veterinary_care_data)
        veterinary = Veterinary.objects.create(veterinary_care=veterinary_care, **validated_data)
        return veterinary

    def update(self, instance, validated_data):
        """
        Обновление существующей записи о ветобработке.
        """
        veterinary_care_data = validated_data.pop('veterinary_care', None)

        if veterinary_care_data:
            veterinary_care = instance.veterinary_care
            veterinary_care.care_type = veterinary_care_data.get('care_type', veterinary_care.care_type)
            veterinary_care.care_name = veterinary_care_data.get('care_name', veterinary_care.care_name)
            veterinary_care.medication = veterinary_care_data.get('medication', veterinary_care.medication)
            veterinary_care.purpose = veterinary_care_data.get('purpose', veterinary_care.purpose)
            veterinary_care.save()

        instance.place = validated_data.get('place', instance.place)
        instance.status = validated_data.get('status', instance.status)
        instance.date_of_care = validated_data.get('date_of_care', instance.date_of_care)
        instance.comments = validated_data.get('comments', instance.comments)
        instance.save()

        return instance


# Сериализатор для бирки (Tag)
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'

    def update(self, instance, validated_data):
        new_tag_number = validated_data.get('tag_number', instance.tag_number)

        if new_tag_number and new_tag_number != instance.tag_number:
            instance.update_tag(new_tag_number)  # Вызываем метод для обновления бирки
        
        return instance

class WeightRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeightRecord
        fields = '__all__'

    def create(self, validated_data):
        """
        Создание новой записи веса.
        """
        return WeightRecord.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Обновление существующей записи веса.
        """
        instance.weight = validated_data.get('weight', instance.weight)
        # Проверяем, если дата перевода вручную не указана, обновляем на текущую
        weight_date = validated_data.get('weight_date', None)
        if weight_date is None:
            instance.weight_date = timezone.now()  # Обновляем на текущую дату
        else:
            instance.weight_date = weight_date  # Устанавливаем вручную, если передана
        instance.save()
        return instance

# Сериализатор для изменения веса
class WeightChangeSerializer(serializers.Serializer):
    date = serializers.DateField()
    weight = serializers.DecimalField(max_digits=5, decimal_places=2)
    change = serializers.DecimalField(max_digits=5, decimal_places=2)


    
