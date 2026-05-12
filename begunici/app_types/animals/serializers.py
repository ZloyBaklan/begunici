from rest_framework import serializers
from django.utils import timezone
from django.db import models
from django.urls import reverse
from decimal import Decimal
from .models import Maker, Ram, Ewe, Sheep, Lambing, AnimalBase, CalendarNote
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
    mother = serializers.CharField(read_only=True)  # Для отображения номера бирки матери
    mother_display = serializers.SerializerMethodField()  # Для отображения с информацией о ссылке
    
    father = serializers.CharField(read_only=True)  # Для отображения номера бирки отца  
    father_display = serializers.SerializerMethodField()  # Для отображения с информацией о ссылке
    children = serializers.SerializerMethodField()
    
    # Поле возраста в новом формате
    age = serializers.SerializerMethodField()
    
    # Поле для даты присвоения статуса
    status_date = serializers.DateField(write_only=True, required=False)
    # Поле для номера акта при архивировании со статусом "Убыл"
    act_number = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=255,
    )
    
    # Поле для отображения кровности по основной породе с форматированием
    dorper_display = serializers.SerializerMethodField()

    class Meta:
        model = AnimalBase
        fields = "__all__"
    
    def get_dorper_display(self, obj):
        """Возвращает отформатированную кровность по основной породе с процентом и звездочкой для ручных значений"""
        if obj.dorper_percentage is None:
            return None
        
        # Форматируем процент (убираем лишние нули)
        percentage = float(obj.dorper_percentage)
        if percentage == int(percentage):
            formatted = f"{int(percentage)}%"
        else:
            formatted = f"{percentage:g}%"
        
        # Добавляем звездочку для ручных значений
        if obj.is_manual_dorper:
            formatted += "*"
            
        return formatted

    def validate_birth_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Дата рождения не может быть в будущем.")
        return value
    
    def validate_dorper_percentage(self, value):
        """Валидация кровности по основной породе (0-100%)"""
        if value is not None:
            if value < 0 or value > 100:
                raise serializers.ValidationError("Кровность по основной породе должна быть в диапазоне от 0 до 100%.")
        return value

    def validate_date_otbivka(self, value):
        if value and value > timezone.now().date():
            raise serializers.ValidationError("Дата отбивки не может быть в будущем.")
        return value

    def validate_carcass_weight(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Вес туши не может быть отрицательным.")
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
        instance = super().create(validated_data)
        
        # Создаем подробный лог создания
        from .models_user_log import UserActionLog
        from django.contrib.auth.models import AnonymousUser
        import pytz
        
        # Получаем текущий запрос из контекста (если доступен)
        request = self.context.get('request')
        if request and not isinstance(request.user, AnonymousUser):
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Переводим тип животного на русский
            animal_type_translations = {
                'Maker': 'Баран-Производитель',
                'Ram': 'Баранчик',
                'Ewe': 'Ярка',
                'Sheep': 'Овцематка'
            }
            
            english_type = instance.get_animal_type()
            russian_type = animal_type_translations.get(english_type, english_type)
            
            # Формируем детали создания
            details = []
            details.append(f"Создан {tag_number}")
            if instance.birth_date:
                details.append(f"Дата рождения: {instance.birth_date.strftime('%d.%m.%Y')}")
            if instance.place:
                details.append(f"Место: {instance.place.sheepfold}")
            if instance.animal_status:
                # Ограничиваем длину статуса
                status_name = instance.animal_status.status_type
                if len(status_name) > 15:
                    status_name = status_name[:15] + "..."
                details.append(f"Статус: {status_name}")
            
            details_text = "; ".join(details)
            
            UserActionLog.objects.create(
                user=request.user,
                action_type="Создание животного",
                object_type=russian_type,
                object_id=tag_number,
                description=details_text
            )
        
        return instance

    def update(self, instance, validated_data):
        # Сохраняем старые значения для истории
        old_status = instance.animal_status
        old_place = instance.place
        
        # Извлекаем дату статуса если она передана
        status_date = validated_data.pop("status_date", None)
        # Извлекаем номер акта (для статуса "Убыл")
        act_number = (validated_data.pop("act_number", "") or "").strip()

        selected_status = validated_data.get("animal_status")
        if selected_status and selected_status.status_type == "Убыл" and act_number:
            prefix = f"Номер акта: {act_number}"
            existing_note = validated_data.get("note")
            if existing_note is None:
                existing_note = instance.note or ""

            if existing_note:
                if not str(existing_note).startswith(prefix):
                    validated_data["note"] = f"{prefix}\n{existing_note}"
            else:
                validated_data["note"] = prefix
        
        # Создаем список изменений для лога
        changes = []
        
        # Проверяем изменения полей
        if 'animal_status' in validated_data and validated_data['animal_status'] != old_status:
            old_status_name = old_status.status_type if old_status else 'Нет статуса'
            new_status_name = validated_data['animal_status'].status_type
            
            # Проверяем, является ли новый статус архивным
            archive_statuses = ['Продажа на мясо', 'Продажа на племя', 'Убыл', 'Убой']
            if new_status_name in archive_statuses:
                # Это архивирование
                changes.append(f"{old_status_name} → {new_status_name}")
                # Добавляем дату архивирования если есть
                if status_date:
                    archive_date_str = status_date.strftime('%d.%m.%Y')
                    changes.append(f"Дата архивирования: {archive_date_str}")
            elif old_status and old_status.status_type in archive_statuses:
                # Это восстановление из архива
                changes.append(f"Восстановление из архива: {old_status_name} → {new_status_name}")
            else:
                # Обычное изменение статуса
                changes.append(f"Статус: {old_status_name} → {new_status_name}")
        
        if 'place' in validated_data and validated_data['place'] != old_place:
            old_place_name = old_place.sheepfold if old_place else 'Нет места'
            new_place_name = validated_data['place'].sheepfold
            changes.append(f"Место: {old_place_name} → {new_place_name}")
        
        # Проверяем изменение бирки
        new_tag = validated_data.get("tag", None)
        if new_tag and isinstance(new_tag, str) and instance.tag.tag_number != new_tag:
            changes.append(f"Бирка: {instance.tag.tag_number} → {new_tag}")
        
        # Проверяем другие важные поля
        field_names = {
            'birth_date': 'Дата рождения',
            'note': 'Примечание',
            'plemstatus': 'Племенной статус',
            'working_condition': 'Рабочее состояние',
            'carcass_weight': 'Вес туши (кг)',
        }
        
        for field, display_name in field_names.items():
            if field in validated_data:
                old_value = getattr(instance, field, None)
                new_value = validated_data[field]
                if old_value != new_value:
                    old_str = str(old_value) if old_value else 'Не указано'
                    new_str = str(new_value) if new_value else 'Не указано'
                    if len(old_str) > 30:
                        old_str = old_str[:30] + '...'
                    if len(new_str) > 30:
                        new_str = new_str[:30] + '...'
                    changes.append(f"{display_name}: {old_str} → {new_str}")
        
        # Проверяем изменения родителей
        if 'mother' in validated_data:
            old_mother = instance.mother
            new_mother = validated_data['mother']
            if old_mother != new_mother:
                old_mother_str = old_mother if old_mother else 'Не указана'
                new_mother_str = new_mother if new_mother else 'Не указана'
                changes.append(f"Мать: {old_mother_str} → {new_mother_str}")
        
        if 'father' in validated_data:
            old_father = instance.father
            new_father = validated_data['father']
            if old_father != new_father:
                old_father_str = old_father if old_father else 'Не указан'
                new_father_str = new_father if new_father else 'Не указан'
                changes.append(f"Отец: {old_father_str} → {new_father_str}")
        
        # Обновление бирки (поле tag приходит из source='tag' для tag_number)
        new_tag = validated_data.pop("tag", None)  # Убираем из validated_data
        if new_tag:
            # Если передана строка (номер бирки), обновляем
            if isinstance(new_tag, str) and instance.tag.tag_number != new_tag:
                instance.tag.update_tag(new_tag)
        
        # Проверяем, изменится ли статус
        new_status = validated_data.get('animal_status')
        status_will_change = new_status and old_status != new_status
        
        # Проверяем, изменится ли место
        new_place = validated_data.get('place')
        place_will_change = new_place and old_place != new_place
        
        # Если статус изменится и передана дата, пропускаем автоматическое создание StatusHistory
        skip_status_history = status_will_change and status_date is not None
        
        # Обновляем поля через super(), передавая параметр skip_status_history
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save(skip_status_history=skip_status_history)
        
        # Если изменился статус и передана дата статуса
        if status_will_change and status_date:
            from datetime import datetime
            from django.utils import timezone
            import pytz
            
            # НЕ обновляем date_of_status в Status - это поле используется всеми животными!
            # Используем только StatusHistory для хранения даты присвоения статуса конкретному животному
            
            # Создаем запись в истории с пользовательской датой в московском времени
            from begunici.app_types.veterinary.vet_models import StatusHistory
            
            # Создаем datetime в московском часовом поясе
            moscow_tz = pytz.timezone('Europe/Moscow')
            status_datetime_moscow = moscow_tz.localize(datetime.combine(status_date, datetime.min.time()))
            
            StatusHistory.objects.create(
                tag=instance.tag,
                old_status=old_status,
                new_status=instance.animal_status,
                change_date=status_datetime_moscow
            )
        
        # Если изменилось место, создаем запись в PlaceMovement
        if place_will_change:
            from begunici.app_types.veterinary.vet_models import PlaceMovement
            
            # Создаем запись о перемещении (дата устанавливается автоматически в методе save)
            movement = PlaceMovement.objects.create(
                tag=instance.tag,
                old_place=old_place,
                new_place=new_place
            )
        
        # Создаем подробный лог изменений
        if changes:
            from .models_user_log import UserActionLog
            from django.contrib.auth.models import AnonymousUser
            import pytz
            
            # Получаем текущий запрос из контекста (если доступен)
            request = self.context.get('request')
            if request and not isinstance(request.user, AnonymousUser):
                moscow_tz = pytz.timezone('Europe/Moscow')
                
                # Переводим тип животного на русский
                animal_type_translations = {
                    'Maker': 'Баран-Производитель',
                    'Ram': 'Баранчик',
                    'Ewe': 'Ярка',
                    'Sheep': 'Овцематка'
                }
                
                english_type = instance.get_animal_type()
                russian_type = animal_type_translations.get(english_type, english_type)
                
                # Определяем тип действия
                action_type = "Редактирование животного"
                new_status = validated_data.get('animal_status')
                if new_status and new_status.status_type in ['Продажа на мясо', 'Продажа на племя', 'Убыл', 'Убой']:
                    action_type = "Архивирование животного"
                elif old_status and old_status.status_type in ['Продажа на мясо', 'Продажа на племя', 'Убыл', 'Убой'] and new_status:
                    action_type = "Восстановление из архива"
                
                changes_text = "; ".join(changes)
                UserActionLog.objects.create(
                    user=request.user,
                    action_type=action_type,
                    object_type=russian_type,
                    object_id=instance.tag.tag_number,
                    description=f"Изменения: {changes_text}"
                )
        
        return instance

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
        Возвращаем дату архивирования на основе последней записи в StatusHistory.
        """
        if obj.is_archived and obj.animal_status:
            # Ищем самую последнюю запись в истории статусов для этого животного (по ID, который автоинкрементный)
            from begunici.app_types.veterinary.vet_models import StatusHistory
            last_status_change = StatusHistory.objects.filter(
                tag=obj.tag,
                new_status=obj.animal_status
            ).order_by('-id').first()  # Сортируем по ID (последняя созданная запись)
            
            if last_status_change:
                return last_status_change.change_date
        return None

    def get_mother_display(self, obj):
        """Получить отображение матери с информацией о ссылке"""
        mother_display = obj.get_mother_display()
        if mother_display and mother_display.get('tag_obj'):
            # Заменяем Tag объект на сериализованные данные
            mother_display['tag_obj'] = TagSerializer(mother_display['tag_obj']).data
        return mother_display

    def get_father_display(self, obj):
        """Получить отображение отца с информацией о ссылке"""
        father_display = obj.get_father_display()
        if father_display and father_display.get('tag_obj'):
            # Заменяем Tag объект на сериализованные данные
            father_display['tag_obj'] = TagSerializer(father_display['tag_obj']).data
        return father_display

    def get_age(self, obj):
        """Возвращает возраст в новом формате 'X мес. (Y сут.)'"""
        return obj.get_age_display()



class MakerSerializer(AnimalBaseSerializer):
    name = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)
    plemstatus = serializers.CharField(max_length=200)
    working_condition = serializers.CharField(max_length=200)
    working_condition_date = serializers.DateField(
        required=False, allow_null=True
    )  # Добавляем поле даты
    display_name = serializers.SerializerMethodField()

    class Meta(AnimalBaseSerializer.Meta):
        model = Maker
        fields = "__all__"

    def get_children(self, obj):
        children = obj.get_children()
        return UniversalChildSerializer(children, many=True).data
    
    def get_display_name(self, obj):
        """Возвращает отображаемое имя для фронтенда"""
        return obj.get_display_name()

    def get_display_name(self, obj):
        """Возвращает отображаемое имя для фронтенда"""
        return obj.get_display_name()



class UniversalChildSerializer(serializers.Serializer):
    """Универсальный сериализатор для детей любого типа животного"""
    tag_number = serializers.SerializerMethodField()
    animal_type = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    link = serializers.SerializerMethodField()
    is_archived = serializers.BooleanField(read_only=True)
    archive_status = serializers.SerializerMethodField()
    archive_date = serializers.SerializerMethodField()
    first_weight = serializers.SerializerMethodField()

    def get_tag_number(self, obj):
        if not obj.tag:
            return "Нет бирки"
        
        # Для баранов-производителей проверяем наличие имени
        if hasattr(obj, 'name') and obj.name:
            return f"{obj.name}({obj.tag.tag_number})"
        
        return obj.tag.tag_number
    
    def get_animal_type(self, obj):
        if not obj.tag:
            return "Неизвестно"
        
        # Словарь для перевода типов животных на русский язык
        type_translations = {
            'Maker': 'Баран-Производитель',
            'Ram': 'Баранчик',
            'Ewe': 'Ярка', 
            'Sheep': 'Овцематка'
        }
        
        english_type = obj.tag.animal_type
        return type_translations.get(english_type, english_type)

    def get_archive_status(self, obj):
        return obj.animal_status.status_type if obj.animal_status else None

    def get_archive_date(self, obj):
        """Получаем дату архивирования из StatusHistory"""
        if not obj.animal_status:
            return None
        
        # Ищем последнюю запись в StatusHistory, где животное получило текущий архивный статус
        from begunici.app_types.veterinary.vet_models import StatusHistory
        
        archive_statuses = ['Убыл', 'Убой', 'Продажа на мясо', 'Продажа на племя']
        if obj.animal_status.status_type in archive_statuses:
            status_history = StatusHistory.objects.filter(
                tag=obj.tag,
                new_status=obj.animal_status
            ).order_by('-change_date').first()
            
            if status_history:
                return status_history.change_date
        
        return None

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

    def get_age(self, obj):
        """Возвращает возраст в новом формате 'X мес. (Y сут.)'"""
        return obj.get_age_display()


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
        # Получаем все окоты для овцематки
        lambings = Lambing.objects.filter(sheep=obj).order_by('-start_date')
        return LambingSerializer(lambings, many=True).data
    
    def get_active_lambings(self, obj):
        """Получаем активные окоты для овцематки"""
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
    father_display_name = serializers.SerializerMethodField()  # Новое поле
    mother_type = serializers.SerializerMethodField()
    father_type = serializers.SerializerMethodField()
    mother_found = serializers.SerializerMethodField()  # Новое поле
    
    # Поля для записи
    mother_tag_number = serializers.CharField(write_only=True, required=False)
    father_tag_number = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = Lambing
        fields = [
            'id', 'start_date', 'planned_lambing_date', 'actual_lambing_date',
            'number_of_lambs', 'dead_lambs_count', 'note', 'is_active', 'created_at',
            'mother_tag', 'father_tag', 'father_display_name', 'mother_type', 'father_type', 'mother_found',
            'mother_tag_number', 'father_tag_number',
            'mother_tag_text', 'mother_type_text'  # Добавляем новые поля
        ]
        read_only_fields = ['id', 'planned_lambing_date', 'created_at']
    
    def get_mother_tag(self, obj):
        try:
            return obj.get_mother_tag()
        except Exception:
            return None
    
    def get_father_tag(self, obj):
        try:
            father = obj.get_father()
            if father and father.tag:
                # Возвращаем только номер бирки для URL
                return father.tag.tag_number
            return None
        except Exception:
            return None
    
    def get_father_display_name(self, obj):
        try:
            father = obj.get_father()
            if father and father.tag:
                # Если отец - баран-производитель с именем, возвращаем Имя(Бирка)
                if hasattr(father, 'name') and father.name:
                    return f"{father.name}({father.tag.tag_number})"
                return father.tag.tag_number
            return None
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
    
    def get_mother_found(self, obj):
        """Возвращает True если мать найдена в БД, False если только текстовые данные"""
        return bool(obj.sheep or obj.ewe)
    
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
                    f"Мать с биркой {mother_tag_number} не найдена среди овцематок и ярок"
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
                    f"Отец с биркой {father_tag_number} не найден среди баранов-производителей и баранчиков"
                )
        
        # Проверяем, что у матери нет активного окота
        # Временно отключено для отладки
        # if mother:
        #     # Проверяем активные окоты в зависимости от типа матери
        #     if data.get('sheep'):  # Если мать - овцематка
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
        # Рассчитываем планируемую дату окота (150 дней от начала)
        if 'start_date' in validated_data and not validated_data.get('planned_lambing_date'):
            from datetime import timedelta
            validated_data['planned_lambing_date'] = validated_data['start_date'] + timedelta(days=150)
        
        return super().create(validated_data)


class ArchiveAnimalSerializer(serializers.Serializer):
    """
    Polymorphic serializer for archive animal lists.
    """

    tag_number = serializers.CharField()
    animal_type = serializers.CharField()
    status = serializers.CharField(source="animal_status__status_type", allow_null=True)
    place = serializers.CharField(source="place__sheepfold", allow_null=True)
    birth_date = serializers.DateField()
    age = serializers.SerializerMethodField()

    @staticmethod
    def _format_weight(value):
        if value is None:
            return None
        try:
            decimal_value = Decimal(value)
        except Exception:
            return None
        return f"{decimal_value:.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _get_last_live_weight(tag_obj):
        if not tag_obj:
            return None

        last_weight = (
            WeightRecord.objects.filter(tag=tag_obj)
            .order_by("-weight_date", "-id")
            .first()
        )
        if not last_weight:
            return None

        return ArchiveAnimalSerializer._format_weight(last_weight.weight)

    @staticmethod
    def _build_mother_url(mother_tag):
        if not mother_tag:
            return None

        if Ewe.objects.filter(tag__tag_number=mother_tag).exists():
            return reverse("animals:ewe-detail", kwargs={"tag_number": mother_tag})
        if Sheep.objects.filter(tag__tag_number=mother_tag).exists():
            return reverse("animals:sheep-detail", kwargs={"tag_number": mother_tag})
        return None

    @staticmethod
    def _format_age_at_date(birth_date, reference_date):
        if not birth_date:
            return None

        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        try:
            if isinstance(birth_date, str):
                birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
            elif hasattr(birth_date, "date"):
                birth_date = birth_date.date()

            if hasattr(reference_date, "date"):
                reference_date = reference_date.date()
            if reference_date is None:
                reference_date = timezone.now().date()

            # Защита от неконсистентных данных
            if reference_date < birth_date:
                return "0 мес."

            delta = relativedelta(reference_date, birth_date)
            total_months = delta.years * 12 + delta.months
            days = round(delta.days)

            if total_months == 0 and days == 0:
                return "0 мес."
            if total_months == 0:
                return f"{days} сут."
            if days == 0:
                return f"{total_months} мес."
            return f"{total_months} мес. ({days} сут.)"
        except (ValueError, TypeError):
            return None

    def to_representation(self, instance):
        from begunici.app_types.veterinary.vet_models import StatusHistory
        from begunici.app_types.animals.models import Tag

        if isinstance(instance, dict):
            tag_number = instance.get("tag__tag_number") or instance.get("tag_number")
            animal_type = instance.get("tag__animal_type") or instance.get("animal_type")
            status_type = instance.get("animal_status__status_type") or "Нет данных"

            archived_date = None
            tag_obj = None
            if tag_number:
                try:
                    tag_obj = Tag.objects.get(tag_number=tag_number)
                except Tag.DoesNotExist:
                    tag_obj = None

            if status_type and tag_obj:
                last_status_change = (
                    StatusHistory.objects.filter(
                        tag=tag_obj,
                        new_status__status_type=status_type,
                    )
                    .order_by("-id")
                    .first()
                )
                if last_status_change:
                    archived_date = last_status_change.change_date

            birth_date_value = instance.get("birth_date")
            age_display = self._format_age_at_date(birth_date_value, archived_date)

            mother_tag = (instance.get("mother") or "").strip() or None
            return {
                "tag_number": tag_number or "Нет данных",
                "animal_type": animal_type or "Unknown",
                "display_name": tag_number or "Нет данных",
                "status": status_type,
                "status_color": instance.get("animal_status__color", "#FFFFFF"),
                "archived_date": archived_date,
                "place": instance.get("place__sheepfold") or "Нет данных",
                "birth_date": birth_date_value,
                "age": age_display,
                "is_archived": bool(instance.get("is_archived", False)),
                "last_live_weight": self._get_last_live_weight(tag_obj),
                "carcass_weight": self._format_weight(instance.get("carcass_weight")),
                "mother_tag": mother_tag,
                "mother_url": self._build_mother_url(mother_tag),
            }

        tag_number = instance.tag.tag_number if instance.tag else "Нет данных"
        animal_type = instance.tag.animal_type if instance.tag else "Unknown"

        archived_date = None
        if instance.animal_status and instance.tag:
            last_status_change = (
                StatusHistory.objects.filter(
                    tag=instance.tag,
                    new_status=instance.animal_status,
                )
                .order_by("-id")
                .first()
            )
            if last_status_change:
                archived_date = last_status_change.change_date

        mother_tag = (instance.mother or "").strip() or None
        age_display = self._format_age_at_date(instance.birth_date, archived_date)

        return {
            "tag_number": tag_number,
            "animal_type": animal_type,
            "display_name": instance.get_display_name() if hasattr(instance, "get_display_name") else tag_number,
            "status": instance.animal_status.status_type if instance.animal_status else "Нет данных",
            "status_color": instance.animal_status.color if instance.animal_status else "#FFFFFF",
            "archived_date": archived_date,
            "place": instance.place.sheepfold if instance.place else "Нет данных",
            "birth_date": instance.birth_date,
            "age": age_display,
            "is_archived": instance.is_archived,
            "last_live_weight": self._get_last_live_weight(instance.tag),
            "carcass_weight": self._format_weight(instance.carcass_weight),
            "mother_tag": mother_tag,
            "mother_url": self._build_mother_url(mother_tag),
        }

    def get_age(self, obj):
        if isinstance(obj, dict):
            return None
        return obj.get_age_display()


class CalendarNoteSerializer(serializers.ModelSerializer):
    """
    Сериализатор для заметок календаря
    """
    formatted_text = serializers.SerializerMethodField()
    
    class Meta:
        model = CalendarNote
        fields = ['id', 'date', 'text', 'formatted_text', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_formatted_text(self, obj):
        """
        Возвращает текст с преобразованными ссылками на животных
        """
        return obj.get_formatted_text()

    def create(self, validated_data):
        # Создаем заметку
        note = CalendarNote.objects.create(**validated_data)
        
        # Создаем подробный лог создания
        from .models_user_log import UserActionLog
        from django.contrib.auth.models import AnonymousUser
        import pytz
        
        # Получаем текущий запрос из контекста (если доступен)
        request = self.context.get('request')
        if request and not isinstance(request.user, AnonymousUser):
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Преобразуем дату в московское время
            date_moscow = note.date
            date_str = date_moscow.strftime('%d.%m.%Y')
            
            # Не включаем текст заметки в лог (может быть длинным)
            UserActionLog.objects.create(
                user=request.user,
                action_type="Создание заметки календаря",
                object_type="Заметка календаря",
                object_id=date_str,  # Используем дату как ID
                description=f"Создана заметка на {date_str}"
            )
        
        return note

    def update(self, instance, validated_data):
        # Создаем список изменений для лога
        changes = []
        
        # Проверяем изменения полей
        old_date = instance.date
        new_date = validated_data.get("date", instance.date)
        if old_date != new_date:
            old_date_str = old_date.strftime('%d.%m.%Y')
            new_date_str = new_date.strftime('%d.%m.%Y')
            changes.append(f"Дата: {old_date_str} → {new_date_str}")
        
        old_text = instance.text
        new_text = validated_data.get("text", instance.text)
        if old_text != new_text:
            changes.append("Текст заметки изменен")  # Не показываем сам текст
        
        # Обновляем поля
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Создаем подробный лог изменений
        if changes:
            from .models_user_log import UserActionLog
            from django.contrib.auth.models import AnonymousUser
            import pytz
            
            # Получаем текущий запрос из контекста (если доступен)
            request = self.context.get('request')
            if request and not isinstance(request.user, AnonymousUser):
                moscow_tz = pytz.timezone('Europe/Moscow')
                
                changes_text = "; ".join(changes)
                date_str = instance.date.strftime('%d.%m.%Y')
                
                UserActionLog.objects.create(
                    user=request.user,
                    action_type="Редактирование заметки календаря",
                    object_type="Заметка календаря",
                    object_id=date_str,  # Используем дату как ID
                    description=f"Изменения заметки на {date_str}: {changes_text}"
                )
        
        return instance


