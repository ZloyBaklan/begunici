from rest_framework import serializers
from django.utils import timezone
from django.db import models
from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase
from begunici.app_types.veterinary.vet_models import (
    Place,
    PlaceMovement,
    Tag,
    Status,
    Veterinary,
    WeightRecord,
    StatusHistory,
)
from begunici.app_types.veterinary.vet_serializers import (
    StatusSerializer,
    PlaceSerializer,
    WeightRecordSerializer,
    VeterinarySerializer,
    TagSerializer,
    PlaceMovementSerializer,
    StatusHistorySerializer,
)


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    Сериализатор с динамическими полями. Позволяет включать/исключать поля через запросы.
    """

    def __init__(self, *args, **kwargs):
        fields = kwargs.pop("fields", None)
        super().__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class AnimalBaseSerializer(DynamicFieldsModelSerializer):
    animal_status = StatusSerializer(
        read_only=True
    )  # Для чтения используется StatusSerializer
    animal_status_id = serializers.PrimaryKeyRelatedField(
        queryset=Status.objects.all(), write_only=True, source="animal_status"
    )  # Для записи используется PrimaryKeyRelatedField
    tag_number = serializers.CharField(write_only=True, source='tag') # Для записи
    tag = TagSerializer(read_only=True) # Для чтения
    # tag_number = serializers.CharField(source='tag.tag_number', write_only=True)  # Для ввода номера бирки
    weight_records = serializers.SerializerMethodField()
    veterinary_history = serializers.SerializerMethodField()
    place = PlaceSerializer(read_only=True)  # Для чтения полного объекта
    place_id = serializers.PrimaryKeyRelatedField(
        queryset=Place.objects.all(), write_only=True, source="place"
    )  # Для записи идентификатора места
    is_archived = serializers.BooleanField(read_only=True)
    archived_date = (
        serializers.SerializerMethodField()
    )  # Новое поле для даты архивирования
    mother = TagSerializer(read_only=True)  # Для отображения полной информации о матери
    mother_id = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        write_only=True,
        source="mother",
        allow_null=True,
        required=False,
    )  # Для указания идентификатора матери

    father = TagSerializer(read_only=True)  # Для отображения полной информации об отце
    father_id = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        write_only=True,
        source="father",
        allow_null=True,
        required=False,
    )  # Для указания идентификатора отца
    children = serializers.SerializerMethodField()

    class Meta:
        model = AnimalBase
        fields = "__all__"

    def validate_birth_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Дата рождения не может быть в будущем.")
        return value

    def create(self, validated_data):
        tag_data = validated_data.pop('tag')
        # tag_data содержит строку номера бирки из поля tag_number
        tag_number = tag_data if isinstance(tag_data, str) else str(tag_data)

        if (Maker.objects.filter(tag__tag_number=tag_number).exists() or
            Ram.objects.filter(tag__tag_number=tag_number).exists() or
            Ewe.objects.filter(tag__tag_number=tag_number).exists() or
            Sheep.objects.filter(tag__tag_number=tag_number).exists()):
            raise serializers.ValidationError({"tag": "Бирка с таким номером уже используется."})

        tag, created = Tag.objects.get_or_create(tag_number=tag_number)
        animal_type = self.Meta.model.__name__
        tag.animal_type = animal_type
        tag.save()

        validated_data['tag'] = tag
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Сохраняем старые значения для истории
        old_status = instance.animal_status
        old_place = instance.place
        
        # Обновление бирки (поле tag приходит из source='tag' для tag_number)
        new_tag = validated_data.pop("tag", None)
        if new_tag:
            # Если передана строка (номер бирки), обновляем
            if isinstance(new_tag, str) and instance.tag.tag_number != new_tag:
                instance.tag.update_tag(new_tag)
        
        # Обновляем поля через super()
        updated_instance = super().update(instance, validated_data)
        
        # StatusHistory и PlaceMovement создаются автоматически в методе save модели AnimalBase
        # Убираем дублирование - не создаем здесь
        
        return updated_instance

    def get_weight_records(self, obj):
        # Получаем записи веса через тег
        weight_records = WeightRecord.objects.filter(tag=obj.tag).order_by(
            "-weight_date"
        )
        return WeightRecordSerializer(weight_records, many=True).data

    def get_veterinary_history(self, obj):
        # Получаем записи ветобработок через тег
        vet_history = (
            Veterinary.objects.filter(tag=obj.tag)
            .select_related("veterinary_care")
            .order_by("-date_of_care")
        )
        return VeterinarySerializer(vet_history, many=True).data

    def get_archived_date(self, obj):
        """
        Возвращаем дату архивирования на основе даты статуса.
        """
        if obj.is_archived and obj.animal_status:
            return obj.animal_status.date_of_status
        return None



class MakerSerializer(AnimalBaseSerializer):
    plemstatus = serializers.CharField(max_length=200)
    working_condition = serializers.CharField(max_length=200)
    working_condition_date = serializers.DateField(
        required=False, allow_null=True
    )  # Добавляем поле даты

    class Meta(AnimalBaseSerializer.Meta):
        model = Maker
        fields = "__all__"

    def get_children(self, obj):
        children = obj.get_children()
        return UniversalChildSerializer(children, many=True).data


class UniversalChildSerializer(serializers.Serializer):
    """Универсальный сериализатор для детей любого типа животного"""
    tag_number = serializers.SerializerMethodField()
    animal_type = serializers.SerializerMethodField()
    age = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    link = serializers.SerializerMethodField()
    is_archived = serializers.BooleanField(read_only=True)
    archive_status = serializers.SerializerMethodField()
    archive_date = serializers.SerializerMethodField()
    first_weight = serializers.SerializerMethodField()

    def get_tag_number(self, obj):
        return obj.tag.tag_number if obj.tag else "Нет бирки"
    
    def get_animal_type(self, obj):
        if not obj.tag:
            return "Неизвестно"
        
        # Словарь для перевода типов животных на русский язык
        type_translations = {
            'Maker': 'Производитель',
            'Ram': 'Баран',
            'Ewe': 'Ярка', 
            'Sheep': 'Овца'
        }
        
        english_type = obj.tag.animal_type
        return type_translations.get(english_type, english_type)

    def get_archive_status(self, obj):
        return obj.animal_status.status_type if obj.animal_status else None

    def get_archive_date(self, obj):
        return obj.animal_status.date_of_status if obj.animal_status else None

    def get_first_weight(self, obj):
        """Возвращает первый (самый ранний) вес животного"""
        if not obj.tag:
            return None
        
        from begunici.app_types.veterinary.vet_models import WeightRecord
        first_weight = WeightRecord.objects.filter(tag=obj.tag).order_by('weight_date').first()
        
        if first_weight:
            return {
                'weight': float(first_weight.weight),
                'date': first_weight.weight_date
            }
        return None

    def get_link(self, obj):
        if not obj.tag:
            return "#"
        
        animal_type_to_route = {
            "Maker": "maker",
            "Sheep": "sheep",
            "Ewe": "ewe",
            "Ram": "ram",
        }
        return f"/animals/{animal_type_to_route.get(obj.tag.animal_type, 'unknown')}/{obj.tag.tag_number}/info/"


class MakerChildSerializer(UniversalChildSerializer):
    pass


class RamChildSerializer(UniversalChildSerializer):
    pass


class EweChildSerializer(UniversalChildSerializer):
    pass


class SheepChildSerializer(UniversalChildSerializer):
    pass


class RamSerializer(AnimalBaseSerializer):
    class Meta(AnimalBaseSerializer.Meta):
        model = Ram
        fields = "__all__"

    def get_children(self, obj):
        children = obj.get_children()
        return UniversalChildSerializer(children, many=True).data


class EweSerializer(AnimalBaseSerializer):
    active_lambings = serializers.SerializerMethodField()
    
    class Meta(AnimalBaseSerializer.Meta):
        model = Ewe
        fields = "__all__"

    def get_children(self, obj):
        children = obj.get_children()
        return UniversalChildSerializer(children, many=True).data
    
    def get_active_lambings(self, obj):
        """Получаем активные окоты для ярки"""
        try:
            lambings = Lambing.objects.filter(ewe=obj, is_active=True)
            return LambingSerializer(lambings, many=True).data
        except Exception as e:
            # В случае ошибки возвращаем пустой список
            return []


class SheepSerializer(AnimalBaseSerializer):
    lambing_history = serializers.SerializerMethodField()
    active_lambings = serializers.SerializerMethodField()

    class Meta(AnimalBaseSerializer.Meta):
        model = Sheep
        fields = "__all__"

    def get_lambing_history(self, obj):
        # Получаем все окоты для овцы
        lambings = Lambing.objects.filter(sheep=obj).order_by('-start_date')
        return LambingSerializer(lambings, many=True).data
    
    def get_active_lambings(self, obj):
        """Получаем активные окоты для овцы"""
        try:
            lambings = Lambing.objects.filter(sheep=obj, is_active=True)
            return LambingSerializer(lambings, many=True).data
        except Exception as e:
            # В случае ошибки возвращаем пустой список
            return []

    def get_children(self, obj):
        # Используем метод get_children из модели Sheep
        children = obj.get_children()
        return UniversalChildSerializer(children, many=True).data


class LambingSerializer(serializers.ModelSerializer):
    # Поля для чтения (отображения)
    mother_tag = serializers.SerializerMethodField()
    father_tag = serializers.SerializerMethodField()
    mother_type = serializers.SerializerMethodField()
    father_type = serializers.SerializerMethodField()
    
    # Поля для записи
    mother_tag_number = serializers.CharField(write_only=True, required=True)
    father_tag_number = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = Lambing
        fields = [
            'id', 'start_date', 'planned_lambing_date', 'actual_lambing_date',
            'number_of_lambs', 'note', 'is_active', 'created_at',
            'mother_tag', 'father_tag', 'mother_type', 'father_type',
            'mother_tag_number', 'father_tag_number'
        ]
        read_only_fields = ['id', 'planned_lambing_date', 'created_at']
    
    def get_mother_tag(self, obj):
        try:
            mother = obj.get_mother()
            return mother.tag.tag_number if mother and mother.tag else None
        except Exception:
            return None
    
    def get_father_tag(self, obj):
        try:
            father = obj.get_father()
            return father.tag.tag_number if father and father.tag else None
        except Exception:
            return None
    
    def get_mother_type(self, obj):
        try:
            return obj.get_mother_type()
        except Exception:
            return None
    
    def get_father_type(self, obj):
        try:
            return obj.get_father_type()
        except Exception:
            return None
    
    def validate(self, data):
        mother_tag_number = data.get('mother_tag_number')
        father_tag_number = data.get('father_tag_number')
        
        # Проверяем существование матери
        mother = None
        try:
            sheep = Sheep.objects.get(tag__tag_number=mother_tag_number)
            mother = sheep
            data['sheep'] = sheep
            data['ewe'] = None
        except Sheep.DoesNotExist:
            try:
                ewe = Ewe.objects.get(tag__tag_number=mother_tag_number)
                mother = ewe
                data['ewe'] = ewe
                data['sheep'] = None
            except Ewe.DoesNotExist:
                raise serializers.ValidationError(
                    f"Мать с биркой {mother_tag_number} не найдена среди овец и ярок"
                )
        
        # Проверяем существование отца
        father = None
        try:
            maker = Maker.objects.get(tag__tag_number=father_tag_number)
            father = maker
            data['maker'] = maker
            data['ram'] = None
        except Maker.DoesNotExist:
            try:
                ram = Ram.objects.get(tag__tag_number=father_tag_number)
                father = ram
                data['ram'] = ram
                data['maker'] = None
            except Ram.DoesNotExist:
                raise serializers.ValidationError(
                    f"Отец с биркой {father_tag_number} не найден среди производителей и баранов"
                )
        
        # Проверяем, что у матери нет активного окота
        # Временно отключено для отладки
        # if mother:
        #     # Проверяем активные окоты в зависимости от типа матери
        #     if data.get('sheep'):  # Если мать - овца
        #         existing_active = Lambing.objects.filter(sheep=data['sheep'], is_active=True)
        #     elif data.get('ewe'):  # Если мать - ярка
        #         existing_active = Lambing.objects.filter(ewe=data['ewe'], is_active=True)
        #     else:
        #         existing_active = Lambing.objects.none()
                
        #     if self.instance:
        #         existing_active = existing_active.exclude(pk=self.instance.pk)
            
        #     if existing_active.exists():
        #         raise serializers.ValidationError(
        #             f"У животного с биркой {mother_tag_number} уже есть активный окот"
        #         )
        
        # Удаляем временные поля
        data.pop('mother_tag_number', None)
        data.pop('father_tag_number', None)
        
        return data
    
    def create(self, validated_data):
        # Рассчитываем планируемую дату окота (6 месяцев от начала)
        if 'start_date' in validated_data and not validated_data.get('planned_lambing_date'):
            from dateutil.relativedelta import relativedelta
            validated_data['planned_lambing_date'] = validated_data['start_date'] + relativedelta(months=6)
        
        return super().create(validated_data)


class ArchiveAnimalSerializer(serializers.Serializer):
    """
    Полиморфный сериализатор для архива животных.
    """

    tag_number = serializers.CharField()
    animal_type = serializers.CharField()
    status = serializers.CharField(source="animal_status__status_type", allow_null=True)
    date_of_status = serializers.DateTimeField(
        source="animal_status__date_of_status", allow_null=True
    )
    place = serializers.CharField(source="place__sheepfold", allow_null=True)
    birth_date = serializers.DateField()
    age = serializers.DecimalField(max_digits=5, decimal_places=1)

    def to_representation(self, instance):
        # Если instance — это словарь (после использования .values())
        if isinstance(instance, dict):
            return {
                "tag_number": instance["tag__tag_number"],
                "animal_type": instance["tag__animal_type"],
                "status": instance.get("animal_status__status_type", "Нет данных"),
                "archived_date": instance["animal_status__date_of_status"],
                "place": instance.get("place__sheepfold", "Нет данных"),
                "birth_date": instance["birth_date"],
                "age": instance["age"],
            }
        # Если instance — это объект модели
        tag_number = instance.tag.tag_number if instance.tag else "Нет данных"
        animal_type = instance.tag.animal_type if instance.tag else "Unknown"
        return {
            "tag_number": tag_number,
            "animal_type": animal_type,
            "status": instance.animal_status.status_type
            if instance.animal_status
            else "Нет данных",
            "archived_date": instance.animal_status.date_of_status
            if instance.animal_status
            else "Нет данных",
            "place": instance.place.sheepfold if instance.place else "Нет данных",
            "birth_date": instance.birth_date,
            "age": instance.age,
        }
