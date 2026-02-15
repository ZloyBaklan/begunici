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
        # Создаем статус
        status = Status.objects.create(**validated_data)
        
        # Создаем подробный лог создания
        from begunici.app_types.animals.models_user_log import UserActionLog
        from django.contrib.auth.models import AnonymousUser
        import pytz
        
        # Получаем текущий запрос из контекста (если доступен)
        request = self.context.get('request')
        if request and not isinstance(request.user, AnonymousUser):
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Преобразуем дату в московское время
            date_moscow = status.date_of_status.astimezone(moscow_tz)
            date_str = date_moscow.strftime('%d.%m.%Y')
            
            UserActionLog.objects.create(
                user=request.user,
                action_type="Создание статуса",
                object_type="Статус",
                object_id=status.status_type,  # Используем название статуса как ID
                description=f"Создан статус '{status.status_type}', дата: {date_str}"
            )
        
        return status

    def update(self, instance, validated_data):
        # Создаем список изменений для лога
        changes = []
        
        # Проверяем изменения полей
        old_status_type = instance.status_type
        new_status_type = validated_data.get("status_type", instance.status_type)
        if old_status_type != new_status_type:
            changes.append(f"Название: {old_status_type} → {new_status_type}")
        
        old_color = instance.color
        new_color = validated_data.get("color", instance.color)
        if old_color != new_color:
            changes.append(f"Цвет: {old_color} → {new_color}")
        
        old_date = instance.date_of_status
        new_date = validated_data.get("date_of_status", None)
        if new_date and old_date != new_date:
            import pytz
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Преобразуем даты в московское время
            old_date_moscow = old_date.astimezone(moscow_tz)
            new_date_moscow = new_date.astimezone(moscow_tz)
            
            old_date_str = old_date_moscow.strftime('%d.%m.%Y')
            new_date_str = new_date_moscow.strftime('%d.%m.%Y')
            changes.append(f"Дата статуса: {old_date_str} → {new_date_str}")
        
        # Обновляем поля
        instance.status_type = new_status_type
        instance.color = new_color
        instance.date_of_status = new_date if new_date else timezone.now()
        instance.save()
        
        # Создаем подробный лог изменений
        if changes:
            from begunici.app_types.animals.models_user_log import UserActionLog
            from django.contrib.auth.models import AnonymousUser
            import pytz
            
            # Получаем текущий запрос из контекста (если доступен)
            request = self.context.get('request')
            if request and not isinstance(request.user, AnonymousUser):
                moscow_tz = pytz.timezone('Europe/Moscow')
                
                changes_text = "; ".join(changes)
                UserActionLog.objects.create(
                    user=request.user,
                    action_type="Редактирование статуса",
                    object_type="Статус",
                    object_id=instance.status_type,  # Используем название статуса как ID
                    description=f"Изменения статуса '{instance.status_type}': {changes_text}"
                )
        
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
        # Создаем овчарню
        place = Place.objects.create(**validated_data)
        
        # Создаем подробный лог создания
        from begunici.app_types.animals.models_user_log import UserActionLog
        from django.contrib.auth.models import AnonymousUser
        import pytz
        
        # Получаем текущий запрос из контекста (если доступен)
        request = self.context.get('request')
        if request and not isinstance(request.user, AnonymousUser):
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Преобразуем дату в московское время
            date_moscow = place.date_of_transfer.astimezone(moscow_tz)
            date_str = date_moscow.strftime('%d.%m.%Y')
            
            UserActionLog.objects.create(
                user=request.user,
                action_type="Создание овчарни",
                object_type="Овчарня",
                object_id=place.sheepfold,  # Используем название овчарни как ID
                description=f"Создана овчарня '{place.sheepfold}', дата: {date_str}"
            )
        
        return place

    def update(self, instance, validated_data):
        # Создаем список изменений для лога
        changes = []
        
        # Проверяем изменения полей
        old_sheepfold = instance.sheepfold
        new_sheepfold = validated_data.get("sheepfold", instance.sheepfold)
        if old_sheepfold != new_sheepfold:
            changes.append(f"Название: {old_sheepfold} → {new_sheepfold}")
        
        old_date = instance.date_of_transfer
        new_date = validated_data.get("date_of_transfer", None)
        if new_date and old_date != new_date:
            import pytz
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Преобразуем даты в московское время
            old_date_moscow = old_date.astimezone(moscow_tz)
            new_date_moscow = new_date.astimezone(moscow_tz)
            
            old_date_str = old_date_moscow.strftime('%d.%m.%Y')
            new_date_str = new_date_moscow.strftime('%d.%m.%Y')
            changes.append(f"Дата перевода: {old_date_str} → {new_date_str}")
        elif new_date is None:
            # Если дата не указана, обновляем на текущую
            new_date = timezone.now()
            import pytz
            moscow_tz = pytz.timezone('Europe/Moscow')
            new_date_moscow = new_date.astimezone(moscow_tz)
            new_date_str = new_date_moscow.strftime('%d.%m.%Y')
            changes.append(f"Дата перевода обновлена на текущую: {new_date_str}")
        
        # Обновляем поля
        instance.sheepfold = new_sheepfold
        instance.date_of_transfer = new_date
        instance.save()
        
        # Создаем подробный лог изменений
        if changes:
            from begunici.app_types.animals.models_user_log import UserActionLog
            from django.contrib.auth.models import AnonymousUser
            import pytz
            
            # Получаем текущий запрос из контекста (если доступен)
            request = self.context.get('request')
            if request and not isinstance(request.user, AnonymousUser):
                moscow_tz = pytz.timezone('Europe/Moscow')
                
                changes_text = "; ".join(changes)
                UserActionLog.objects.create(
                    user=request.user,
                    action_type="Редактирование овчарни",
                    object_type="Овчарня",
                    object_id=instance.sheepfold,  # Используем название овчарни как ID
                    description=f"Изменения овчарни '{instance.sheepfold}': {changes_text}"
                )
        
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

    def create(self, validated_data):
        # Создаем ветеринарную обработку
        care = VeterinaryCare.objects.create(**validated_data)
        
        # Создаем подробный лог создания
        from begunici.app_types.animals.models_user_log import UserActionLog
        from django.contrib.auth.models import AnonymousUser
        import pytz
        
        # Получаем текущий запрос из контекста (если доступен)
        request = self.context.get('request')
        if request and not isinstance(request.user, AnonymousUser):
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Формируем сокращенные детали создания
            details = []
            details.append(f"Тип: {care.care_type}")
            details.append(f"Название: {care.care_name}")
            if care.medication:
                # Ограничиваем длину препарата
                medication = care.medication[:20] + "..." if len(care.medication) > 20 else care.medication
                details.append(f"Препарат: {medication}")
            if care.purpose:
                # Ограничиваем длину цели
                purpose = care.purpose[:15] + "..." if len(care.purpose) > 15 else care.purpose
                details.append(f"Цель: {purpose}")
            if care.default_duration_days > 0:
                details.append(f"Срок: {care.default_duration_days}д")
            else:
                details.append("Срок: бессрочно")
            
            details_text = "; ".join(details)
            care_name = f"{care.care_type} - {care.care_name}"
            
            UserActionLog.objects.create(
                user=request.user,
                action_type="Создание ветеринарной обработки",
                object_type="Ветеринарная обработка",
                object_id=care_name,  # Используем комбинацию типа и названия
                description=f"Создана вет.обработка: {details_text}"
            )
        
        return care

    def update(self, instance, validated_data):
        # Создаем список изменений для лога
        changes = []
        
        # Проверяем изменения полей
        old_care_type = instance.care_type
        new_care_type = validated_data.get("care_type", instance.care_type)
        if old_care_type != new_care_type:
            changes.append(f"Тип: {old_care_type} → {new_care_type}")
        
        old_care_name = instance.care_name
        new_care_name = validated_data.get("care_name", instance.care_name)
        if old_care_name != new_care_name:
            changes.append(f"Название: {old_care_name} → {new_care_name}")
        
        old_medication = instance.medication or "Не указан"
        new_medication = validated_data.get("medication", instance.medication) or "Не указан"
        if old_medication != new_medication:
            # Ограничиваем длину препаратов
            old_med = old_medication[:15] + "..." if len(old_medication) > 15 else old_medication
            new_med = new_medication[:15] + "..." if len(new_medication) > 15 else new_medication
            changes.append(f"Препарат: {old_med} → {new_med}")
        
        old_purpose = instance.purpose or "Не указана"
        new_purpose = validated_data.get("purpose", instance.purpose) or "Не указана"
        if old_purpose != new_purpose:
            # Ограничиваем длину целей
            old_purp = old_purpose[:15] + "..." if len(old_purpose) > 15 else old_purpose
            new_purp = new_purpose[:15] + "..." if len(new_purpose) > 15 else new_purpose
            changes.append(f"Цель: {old_purp} → {new_purp}")
        
        old_duration = instance.default_duration_days
        new_duration = validated_data.get("default_duration_days", instance.default_duration_days)
        if old_duration != new_duration:
            old_duration_str = f"{old_duration}д" if old_duration > 0 else "бессрочно"
            new_duration_str = f"{new_duration}д" if new_duration > 0 else "бессрочно"
            changes.append(f"Срок: {old_duration_str} → {new_duration_str}")
        
        # Обновляем поля
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Создаем подробный лог изменений
        if changes:
            from begunici.app_types.animals.models_user_log import UserActionLog
            from django.contrib.auth.models import AnonymousUser
            import pytz
            
            # Получаем текущий запрос из контекста (если доступен)
            request = self.context.get('request')
            if request and not isinstance(request.user, AnonymousUser):
                moscow_tz = pytz.timezone('Europe/Moscow')
                
                changes_text = "; ".join(changes)
                care_name = f"{instance.care_type} - {instance.care_name}"
                
                UserActionLog.objects.create(
                    user=request.user,
                    action_type="Редактирование ветеринарной обработки",
                    object_type="Ветеринарная обработка",
                    object_id=care_name,  # Используем комбинацию типа и названия
                    description=f"Изменения вет.обработки: {changes_text}"
                )
        
        return instance


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
            'id', 'tag', 'veterinary_care', 'date_of_care', 'duration_days', 'comments',
            'tag_write', 'veterinary_care_write'
        ]

    def validate_date_of_care(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("Дата и время обработки не может быть в будущем.")
        return value

    def create(self, validated_data):
        # Создаем ветеринарную обработку
        veterinary = Veterinary.objects.create(**validated_data)
        
        # Создаем подробный лог создания
        from begunici.app_types.animals.models_user_log import UserActionLog
        from django.contrib.auth.models import AnonymousUser
        import pytz
        
        # Получаем текущий запрос из контекста (если доступен)
        request = self.context.get('request')
        if request and not isinstance(request.user, AnonymousUser):
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Преобразуем дату в московское время
            date_str = veterinary.date_of_care.astimezone(moscow_tz).strftime('%d.%m.%Y')
            
            # Формируем сокращенное описание
            care_name = f"{veterinary.veterinary_care.care_type} - {veterinary.veterinary_care.care_name}"
            if len(care_name) > 30:
                care_name = care_name[:30] + "..."
            
            UserActionLog.objects.create(
                user=request.user,
                action_type="Добавление ветеринарной обработки",
                object_type="Ветеринарная обработка",
                object_id=veterinary.tag.tag_number,
                description=f"Добавлена обработка '{care_name}'; Дата: {date_str}; Бирка: {veterinary.tag.tag_number}"
            )
        
        return veterinary


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

    def create(self, validated_data):
        # Создаем запись о весе
        weight_record = WeightRecord.objects.create(**validated_data)
        
        # Создаем подробный лог создания
        from begunici.app_types.animals.models_user_log import UserActionLog
        from django.contrib.auth.models import AnonymousUser
        import pytz
        
        # Получаем текущий запрос из контекста (если доступен)
        request = self.context.get('request')
        if request and not isinstance(request.user, AnonymousUser):
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            # Преобразуем дату в московское время
            date_str = weight_record.weight_date.strftime('%d.%m.%Y')
            
            UserActionLog.objects.create(
                user=request.user,
                action_type="Добавление записи о весе",
                object_type="Запись о весе",
                object_id=weight_record.tag.tag_number,
                description=f"Добавлен вес {weight_record.weight} кг; Дата: {date_str}; Бирка: {weight_record.tag.tag_number}"
            )
        
        return weight_record

# Сериализатор для изменения веса
class WeightChangeSerializer(serializers.Serializer):
    date = serializers.DateField()
    weight = serializers.DecimalField(max_digits=5, decimal_places=2)
    change = serializers.DecimalField(max_digits=5, decimal_places=2)
