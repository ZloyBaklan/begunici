from rest_framework import serializers
from django.utils import timezone  # Не забудь импортировать timezone

from .vet_models import (
    Veterinary,
    Status,
    StatusHistory,
    Tag,
    VeterinaryCare,
    WeightRecord,
    Place,
    PlaceMovement,
)


# Сериализатор для статусов
class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = "__all__"

    def create(self, validated_data):
        # Логика создания статуса
        status = Status.objects.create(**validated_data)
        return status

    def update(self, instance, validated_data):
        print("Полученные данные:", validated_data)  # Лог входящих данных
        instance.status_type = validated_data.get("status_type", instance.status_type)
        instance.color = validated_data.get("color", instance.color)
        date_of_status = validated_data.get("date_of_status", None)
        instance.date_of_status = (
            date_of_status if date_of_status else timezone.now().date()
        )
        instance.save()
        return instance

    def validate_status_type(self, value):
        """Проверяем, что статус с таким названием уникален."""
        # Получаем текущий экземпляр, если он существует
        instance = getattr(self, "instance", None)
        if instance:
            # Если текущий объект имеет то же значение, пропускаем проверку
            if instance.status_type == value:
                return value
        # Если объект новый или значение изменено, проверяем на уникальность
        if Status.objects.filter(status_type=value).exists():
            raise serializers.ValidationError(
                "Статус с таким названием уже существует."
            )
        return value


class StatusHistorySerializer(serializers.ModelSerializer):
    old_status = StatusSerializer(
        read_only=True
    )  # Отображает старый статус по его `__str__` реализации
    new_status = StatusSerializer(
        read_only=True
    )  # Отображает новый статус по его `__str__` реализации

    class Meta:
        model = StatusHistory
        fields = "__all__"


# Сериализатор для места
class PlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Place
        fields = "__all__"

    def create(self, validated_data):
        # Логика создания места с возможностью установить дату перевода вручную
        return Place.objects.create(**validated_data)

    def update(self, instance, validated_data):
        # Логика обновления места
        instance.sheepfold = validated_data.get("sheepfold", instance.sheepfold)
        # instance.compartment = validated_data.get('compartment', instance.compartment)

        # Проверяем, если дата перевода вручную не указана, обновляем на текущую
        date_of_transfer = validated_data.get("date_of_transfer", None)
        if date_of_transfer is None:
            instance.date_of_transfer = (
                timezone.now().date()
            )  # Обновляем на текущую дату
        else:
            instance.date_of_transfer = (
                date_of_transfer  # Устанавливаем вручную, если передана
            )

        instance.save()
        return instance

    def validate(self, data):
        """
        Проверяем, что сочетание овчарня + отсек уникально.
        """
        sheepfold = data.get("sheepfold")
        # compartment = data.get('compartment')

        if Place.objects.filter(sheepfold=sheepfold).exists():
            raise serializers.ValidationError("Овчарня с таким отсеком уже существует.")
        return data


class PlaceMovementSerializer(serializers.ModelSerializer):
    old_place = PlaceSerializer(read_only=True)
    new_place = PlaceSerializer(read_only=True)

    class Meta:
        model = PlaceMovement
        fields = "__all__"


class VeterinaryCareSerializer(serializers.ModelSerializer):
    class Meta:
        model = VeterinaryCare
        fields = "__all__"

    def create(self, validated_data):
        """
        Создание новой записи ветобработки.
        """
        return VeterinaryCare.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Обновление существующего типа ветобработки.
        """
        instance.care_type = validated_data.get("care_type", instance.care_type)
        instance.care_name = validated_data.get("care_name", instance.care_name)
        instance.medication = validated_data.get("medication", instance.medication)
        instance.purpose = validated_data.get("purpose", instance.purpose)
        instance.save()
        return instance


class VeterinarySerializer(serializers.ModelSerializer):
    veterinary_care = VeterinaryCareSerializer()  # Используем вложенный сериализатор
    tag_number = serializers.CharField(
        source="tag.tag_number", read_only=True
    )  # Добавляем `tag_number`

    class Meta:
        model = Veterinary
        fields = "__all__"

    def create(self, validated_data):
        """
        Создание новой записи о ветобработке для животного.
        """
        veterinary_care_data = validated_data.pop("veterinary_care", None)
        if veterinary_care_data:
            veterinary_care = VeterinaryCare.objects.create(**veterinary_care_data)
        else:
            veterinary_care = None

        veterinary = Veterinary.objects.create(
            veterinary_care=veterinary_care, **validated_data
        )
        return veterinary

    def update(self, instance, validated_data):
        """
        Обновление существующей записи о ветобработке.
        """
        veterinary_care_data = validated_data.pop("veterinary_care", None)

        if veterinary_care_data:
            veterinary_care = instance.veterinary_care
            for field, value in veterinary_care_data.items():
                setattr(veterinary_care, field, value)
            veterinary_care.save()

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()
        return instance


# Сериализатор для бирки (Tag)
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"

    def update(self, instance, validated_data):
        new_tag_number = validated_data.get("tag_number", instance.tag_number)

        if new_tag_number and new_tag_number != instance.tag_number:
            instance.update_tag(new_tag_number)  # Вызываем метод для обновления бирки

        return instance


class WeightRecordSerializer(serializers.ModelSerializer):
    tag_number = serializers.CharField(
        source="tag.tag_number", read_only=True
    )  # Добавляем номер бирки

    def validate_tag_number(self, value):
        """Проверяем, существует ли tag_number"""
        if not Tag.objects.filter(tag_number=value).exists():
            raise serializers.ValidationError("Бирка с таким номером не найдена.")
        return value

    def create(self, validated_data):
        """Подменяем tag_number на объект Tag перед созданием записи"""
        tag_number = validated_data.pop("tag")
        tag = Tag.objects.get(tag_number=tag_number)
        validated_data["tag"] = tag
        return super().create(validated_data)

    class Meta:
        model = WeightRecord
        fields = "__all__"


# Сериализатор для изменения веса
class WeightChangeSerializer(serializers.Serializer):
    date = serializers.DateField()
    weight = serializers.DecimalField(max_digits=5, decimal_places=2)
    change = serializers.DecimalField(max_digits=5, decimal_places=2)
