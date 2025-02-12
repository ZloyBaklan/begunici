from django.db import models
from django.utils import timezone

'''Статус через админку и вебку имеет дату создания, но в случае выставления статуса в поле(его обновления), нужно чтобы дата обновлялась на текущую'''
# Приложение animals

class Tag(models.Model):
    tag_number = models.CharField(max_length=100, unique=True, verbose_name='Бирка')
    animal_type = models.CharField(max_length=100, verbose_name='Тип животного')
    issue_date = models.DateField(auto_now_add=True, verbose_name='Дата выдачи бирки')
    #previous_tags = models.JSONField(default=list, verbose_name='Предыдущие бирки')  # Поле для хранения истории бирок

    def update_tag(self, new_tag_number):
        """
        Обновление бирки животного и сохранение предыдущей бирки.
        """
        if self.tag_number != new_tag_number:  # Проверяем, меняется ли бирка
            #self.previous_tags.append(self.tag_number)  # Добавляем текущую бирку в историю
            self.tag_number = new_tag_number  # Обновляем на новую бирку
            self.save()
    
    def __str__(self):
        return self.tag_number


class Status(models.Model):
    status_type = models.CharField(max_length=200, unique=True, verbose_name='Название статуса')
    date_of_status = models.DateField(verbose_name='Дата статуса', default=timezone.now().date())  # Дата по умолчанию - текущая
    color = models.CharField(max_length=7, unique=True, verbose_name='Цвет статуса', default='#FFFFFF')  # Цвет статуса, по умолчанию белый

    def __str__(self):
        return self.status_type

    

class StatusHistory(models.Model):
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        verbose_name='Бирка',
        related_name='status_history'
    )
    old_status = models.ForeignKey(
        Status,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='old_status',
        verbose_name='Старый статус'
    )
    new_status = models.ForeignKey(
        Status,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='new_status',
        verbose_name='Новый статус'
    )

    def save(self, *args, **kwargs):
        # Обновляем дату перевода в `Place` для нового места
        if self.new_status:
            self.new_status.date_of_status = timezone.now().date()  # Устанавливаем текущую дату перевода
            self.new_status.save()

        super(StatusHistory, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.tag.tag_number}: {self.old_status} -> {self.new_status} ({self.new_status.date_of_status})"



class Place(models.Model):
    sheepfold = models.CharField(max_length=200, verbose_name='Овчарня-Отсек')
    date_of_transfer = models.DateField(verbose_name='Дата перевода', default=timezone.now().date())  # Дата перевода по умолчанию

    def __str__(self):
        return self.sheepfold

class PlaceMovement(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, verbose_name='Бирка', related_name="place_movements")
    old_place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='place_movements_from',
        verbose_name='Предыдущее место'
    )
    new_place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='place_movements_to',
        verbose_name='Новое место'
    )
    class Meta:
        unique_together = ('tag', 'old_place', 'new_place')

    def save(self, *args, **kwargs):
        # Проверяем, существует ли уже такая запись
        if not self.pk and PlaceMovement.objects.filter(
            tag=self.tag,
            old_place=self.old_place,
            new_place=self.new_place
        ).exists():
            return  # Если запись уже существует, не сохраняем её

        # Если указано новое место, обновляем его дату перевода
        if self.new_place:
            self.new_place.date_of_transfer = timezone.now().date()
            self.new_place.save()

        super(PlaceMovement, self).save(*args, **kwargs)

    @property
    def date_of_transfer(self):
        """
        Дата перевода берется из связанного нового места, если оно существует.
        """
        return self.new_place.date_of_transfer if self.new_place else None

    def __str__(self):
        return f"{self.tag.tag_number}: {self.old_place} -> {self.new_place} ({self.date_of_transfer})"



class WeightRecord(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, verbose_name='Бирка')
    weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Вес (кг)')
    weight_date = models.DateField(verbose_name='Дата взвешивания',  default=timezone.now().date())

    def __str__(self):
        return f"Вес: {self.weight} кг, Дата: {self.weight_date}"

    @staticmethod
    def get_weight_history(tag):
        """
        Возвращает всю историю веса для конкретного животного (по бирке).
        """
        return WeightRecord.objects.filter(tag=tag).order_by('weight_date')

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
                weight_changes.append({
                    'date': record.weight_date,
                    'weight': record.weight,
                    'change': change
                })
            previous_weight = record.weight

        return weight_changes

class VeterinaryCare(models.Model):
    care_type = models.CharField(max_length=100, verbose_name='Тип обработки')
    care_name = models.CharField(max_length=200, verbose_name='Название обработки')  # Название прививки/обработки
    medication = models.CharField(max_length=200, verbose_name='Препарат/материал', blank=True, null=True)  # Лекарство или материал, если есть
    purpose = models.CharField(max_length=200, verbose_name='Цель обработки', blank=True, null=True)  # Причина/цель обработки

    def __str__(self):
        return self.care_type
    
    class Meta:
        unique_together = ('care_type', 'care_name', 'medication')
    

class Veterinary(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, verbose_name='Бирка')
    # place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    # status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    veterinary_care = models.ForeignKey(VeterinaryCare, on_delete=models.SET_NULL, null=True, verbose_name='Вет-обработка')
    date_of_care = models.DateField(verbose_name='Дата обработки', default=timezone.now().date())
    comments = models.TextField(verbose_name='Примечания', blank=True, null=True)  # Доп. комментарии

    def __str__(self):
        return f"Ветобработка {self.veterinary_care} для {self.tag.tag_number}"

    class Meta:
        unique_together = ('tag', 'veterinary_care', 'date_of_care')  # Уникальность для комбинации бирка + ветобработка + дата



