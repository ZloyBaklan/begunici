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
    date_of_status = serializers.DateTimeField()
    
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
            date_of_status if date_of_status else timezone.now()
        )
        instance.save()
        return instance

    def validate_date_of_status(self, value):
        if value and value > timezone.now():
            raise serializers.ValidationError("Дата и время статуса не может быть в будущем.")
        return value

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
                timezone.now()
            )  # Обновляем на текущую дату и время
        else:
            instance.date_of_transfer = (
                date_of_transfer  # Устанавливаем вручную, если передана
            )

        instance.save()
        return instance

    def validate_date_of_transfer(self, value):
        if value and value > timezone.now():
            raise serializers.ValidationError("Дата и время перемещения не может быть в будущем.")
        return value

    def validate_sheepfold(self, value):
        """Проверяем, что овчарня с таким названием уникальна."""
        instance = getattr(self, "instance", None)
        query = Place.objects.filter(sheepfold=value)
        if instance:
            query = query.exclude(pk=instance.pk)
        if query.exists():
            raise serializers.ValidationError("Овчарня с таким названием уже существует.")
        return value


class VeterinaryCareSerializer(serializers.ModelSerializer):
    class Meta:
        model = VeterinaryCare
        fields = "__all__"


class PlaceMovementSerializer(serializers.ModelSerializer):
    old_place = PlaceSerializer(read_only=True)
    new_place = PlaceSerializer(read_only=True)

    class Meta:
        model = PlaceMovement
        fields = "__all__"

    def update(self, instance, validated_data):
        """
        Обновление существующего перемещения.
        """
        # Этот метод не должен обновлять ветобработку, исправляем логику
        return instance


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"

    def update(self, instance, validated_data):
        new_tag_number = validated_data.get("tag_number", instance.tag_number)

        if new_tag_number and new_tag_number != instance.tag_number:
            instance.update_tag(new_tag_number)  # Вызываем метод для обновления бирки
        return instance


class VeterinarySerializer(serializers.ModelSerializer):
    # Поля для чтения (read-only)
    tag = TagSerializer(read_only=True)
    veterinary_care = VeterinaryCareSerializer(read_only=True)

    # Поля для записи (write-only)
    tag_write = serializers.SlugRelatedField(
        queryset=Tag.objects.all(),
        slug_field='tag_number',
        write_only=True,
        source='tag'
    )
    veterinary_care_write = serializers.PrimaryKeyRelatedField(
        queryset=VeterinaryCare.objects.all(),
        write_only=True,
        source='veterinary_care'
    )

    class Meta:
        model = Veterinary
        fields = [
            'id', 'tag', 'veterinary_care', 'date_of_care', 'comments',
            'tag_write', 'veterinary_care_write'
        ]

    def validate_date_of_care(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("Дата и время обработки не может быть в будущем.")
        return value


class WeightRecordSerializer(serializers.ModelSerializer):
    # Для чтения
    tag = TagSerializer(read_only=True)
    tag_write = serializers.SlugRelatedField(
        queryset=Tag.objects.all(),
        slug_field='tag_number',
        write_only=True,
        source='tag'
    )

    class Meta:
        model = WeightRecord
        fields = ['id', 'tag', 'weight', 'weight_date', 'tag_write']

# Сериализатор для изменения веса
class WeightChangeSerializer(serializers.Serializer):
    date = serializers.DateField()
    weight = serializers.DecimalField(max_digits=5, decimal_places=2)
    change = serializers.DecimalField(max_digits=5, decimal_places=2)
