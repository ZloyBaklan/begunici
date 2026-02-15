from django.db import models
from django.utils import timezone

"""Статус через админку и вебку имеет дату создания, но в случае выставления статуса в поле(его обновления), нужно чтобы дата обновлялась на текущую"""
# Приложение animals


def get_current_date():
    """Возвращает текущую дату для DateField"""
    return timezone.now().date()


class Tag(models.Model):
    tag_number = models.CharField(max_length=100, unique=True, verbose_name="Бирка")
    animal_type = models.CharField(max_length=100, verbose_name="Тип животного")
    issue_date = models.DateField(auto_now_add=True, verbose_name="Дата выдачи бирки")
    # previous_tags = models.JSONField(default=list, verbose_name='Предыдущие бирки')  # Поле для хранения истории бирок

    def update_tag(self, new_tag_number):
        """
        Обновление бирки животного и сохранение предыдущей бирки.
        """
        if self.tag_number != new_tag_number:  # Проверяем, меняется ли бирка
            # self.previous_tags.append(self.tag_number)  # Добавляем текущую бирку в историю
            self.tag_number = new_tag_number  # Обновляем на новую бирку
            self.save()

    def __str__(self):
        return self.tag_number


class Status(models.Model):
    status_type = models.CharField(
        max_length=200, unique=True, verbose_name="Название статуса"
    )
    date_of_status = models.DateTimeField(
        verbose_name="Дата и время статуса", default=timezone.now
    )  # Дата и время по умолчанию - текущие
    color = models.CharField(
        max_length=7, verbose_name="Цвет статуса", default="#FFFFFF"
    )  # Цвет статуса, по умолчанию белый

    def __str__(self):
        return self.status_type


class StatusHistory(models.Model):
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        verbose_name="Бирка",
        related_name="status_history",
    )
    old_status = models.ForeignKey(
        Status,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="old_status",
        verbose_name="Старый статус",
    )
    new_status = models.ForeignKey(
        Status,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="new_status",
        verbose_name="Новый статус",
    )
    change_date = models.DateTimeField(
        verbose_name="Дата и время изменения", default=timezone.now
    )  # Собственная дата изменения статуса

    def save(self, *args, **kwargs):
        # Убираем логику обновления date_of_status статуса
        # Теперь используем собственное поле change_date
        super(StatusHistory, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.tag.tag_number}: {self.old_status} -> {self.new_status} ({self.change_date})"


class Place(models.Model):
    sheepfold = models.CharField(max_length=200, unique=True, verbose_name="Овчарня-Отсек")
    date_of_transfer = models.DateTimeField(
        verbose_name="Дата и время перевода", default=timezone.now
    )  # Дата и время перевода по умолчанию

    def __str__(self):
        return self.sheepfold


class PlaceMovement(models.Model):
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        verbose_name="Бирка",
        related_name="place_movements",
    )
    old_place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="place_movements_from",
        verbose_name="Предыдущее место",
    )
    new_place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="place_movements_to",
        verbose_name="Новое место",
    )
    created_at = models.DateTimeField(
        verbose_name="Дата и время перемещения",
        default=timezone.now
    )

    class Meta:
        # Убираем unique_together, чтобы разрешить повторные перемещения
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Убираем проверку на существование записи - разрешаем повторные перемещения
        
        # Если указано новое место, обновляем его дату перевода
        if self.new_place:
            self.new_place.date_of_transfer = timezone.now()
            self.new_place.save()

        super(PlaceMovement, self).save(*args, **kwargs)

    @property
    def date_of_transfer(self):
        """
        Дата перевода берется из created_at или из связанного нового места.
        """
        return self.created_at if self.created_at else (self.new_place.date_of_transfer if self.new_place else None)

    def __str__(self):
        return f"{self.tag.tag_number}: {self.old_place} -> {self.new_place} ({self.date_of_transfer})"


class WeightRecord(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, verbose_name="Бирка")
    weight = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="Вес (кг)"
    )
    weight_date = models.DateField(
        verbose_name="Дата взвешивания", default=get_current_date
    )

    def __str__(self):
        return f"Вес: {self.weight} кг, Дата: {self.weight_date}"

    @staticmethod
    def get_weight_history(tag):
        """
        Возвращает всю историю веса для конкретного животного (по бирке).
        """
        return WeightRecord.objects.filter(tag=tag).order_by("weight_date")

    @staticmethod
    def get_weight_changes(tag):
        """
        Возвращает приросты/снижения веса для животного.
        """
        history = WeightRecord.get_weight_history(tag)
        weight_changes = []
        previous_weight = None

        for record in history:
            if previous_weight is not None:
                change = record.weight - previous_weight
                weight_changes.append(
                    {
                        "date": record.weight_date,
                        "weight": record.weight,
                        "change": change,
                    }
                )
            previous_weight = record.weight

        return weight_changes


class VeterinaryCare(models.Model):
    care_type = models.CharField(max_length=100, verbose_name="Тип обработки")
    care_name = models.CharField(
        max_length=200, verbose_name="Название обработки"
    )  # Название прививки/обработки
    medication = models.CharField(
        max_length=200, verbose_name="Препарат/материал", blank=True, null=True
    )  # Лекарство или материал, если есть
    purpose = models.CharField(
        max_length=200, verbose_name="Цель обработки", blank=True, null=True
    )  # Причина/цель обработки
    default_duration_days = models.PositiveIntegerField(
        verbose_name="Срок действия (дней)", 
        default=0,
        help_text="0 = бессрочно"
    )

    def __str__(self):
        return self.care_type

    class Meta:
        unique_together = ("care_type", "care_name", "medication")


class Veterinary(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, verbose_name="Бирка")
    # place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    # status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    veterinary_care = models.ForeignKey(
        VeterinaryCare,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Вет-обработка",
    )
    date_of_care = models.DateTimeField(
        verbose_name="Дата и время обработки", default=timezone.now
    )
    duration_days = models.PositiveIntegerField(
        verbose_name="Срок действия (дней)", 
        default=0,
        help_text="0 = бессрочно"
    )
    comments = models.TextField(
        verbose_name="Примечания", blank=True, null=True
    )  # Доп. комментарии
    is_hidden = models.BooleanField(
        verbose_name="Скрыто из отслеживания",
        default=False,
        help_text="Скрыть из таблицы текущих ветобработок"
    )

    def __str__(self):
        return f"Ветобработка {self.veterinary_care} для {self.tag.tag_number}"
    
    def get_expiry_date(self):
        """Возвращает дату окончания действия ветобработки"""
        if self.duration_days == 0:
            return None  # Бессрочно
        from datetime import timedelta
        
        # Получаем дату из date_of_care (может быть datetime или date)
        if hasattr(self.date_of_care, 'date'):
            care_date = self.date_of_care.date()
        else:
            care_date = self.date_of_care
            
        return care_date + timedelta(days=self.duration_days)
    
    def get_days_remaining(self):
        """Возвращает количество оставшихся дней действия"""
        if self.duration_days == 0:
            return None  # Бессрочно
        
        expiry_date = self.get_expiry_date()
        if expiry_date:
            from datetime import date
            from django.utils import timezone
            
            # Получаем текущую дату в московском времени
            moscow_now = timezone.localtime(timezone.now())
            today = moscow_now.date()
            
            remaining = (expiry_date - today).days
            return remaining
        return None
    
    def is_expired(self):
        """Проверяет, истек ли срок действия"""
        remaining = self.get_days_remaining()
        return remaining is not None and remaining < 0
    
    def is_expiring_today(self):
        """Проверяет, истекает ли срок сегодня"""
        remaining = self.get_days_remaining()
        return remaining is not None and remaining == 0

    class Meta:
        # Убираем ограничение unique_together, чтобы разрешить несколько одинаковых обработок в день
        # unique_together = (
        #     "tag",
        #     "veterinary_care", 
        #     "date_of_care",
        # )
        pass
