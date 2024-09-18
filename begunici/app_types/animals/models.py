from django.db import models
from datetime import date, timedelta
from begunici.app_types.veterinary.models import Tag, Status, Veterinary, Place, WeightRecord, VeterinaryCare


from dateutil.relativedelta import relativedelta

class AnimalBase(models.Model):
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, verbose_name='Бирка', unique=True)
    animal_status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    birth_date = models.DateField(verbose_name='Дата рождения', null=True, blank=True)
    age = models.DecimalField(verbose_name='Возраст (в месяцах)', max_digits=5, decimal_places=1, null=True, blank=True)
    note = models.CharField(max_length=100, verbose_name='Примечание', null=True, blank=True)

    weight_records = models.ManyToManyField(
        WeightRecord,
        related_name='%(class)s_weight_records',
        verbose_name='История взвешиваний',
        blank=True
    )

    veterinary_history = models.ManyToManyField(
        Veterinary,
        related_name='%(class)s_veterinary_history',
        verbose_name='История ветобработок',
        blank=True
    )

    place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        related_name='%(class)s_place_history',
        verbose_name='Место'
    )
    
    class Meta:
        abstract = True

    # Получение даты последнего перевода
    @property
    def last_transfer_date(self):
        return self.place.date_of_transfer if self.place else None

    # Расчет возраста
    def calculate_age(self):
        if self.birth_date and not self.is_archived():
            current_date = date.today()
            delta = relativedelta(current_date, self.birth_date)
            self.age = round(delta.years * 12 + delta.months + delta.days / 30, 1)  # Округляем до 1 знака
            self.save()

    # Проверка, является ли животное архивным
    def is_archived(self):
        return self.animal_status and self.animal_status.status_type in ['Убыл', 'Убой', 'Продажа']

    # Фиксация возраста при смене статуса на архивный
    def set_fixed_age(self):
        if self.is_archived():
            current_date = date.today()
            delta = relativedelta(current_date, self.birth_date)
            self.age = round(delta.years * 12 + delta.months + delta.days / 30, 1)
            self.save()

    # Переопределение метода сохранения
    def save(self, *args, **kwargs):
        if self.is_archived():
            self.set_fixed_age()  # Фиксируем возраст
        else:
            self.calculate_age()  # Рассчитываем возраст
        super(AnimalBase, self).save(*args, **kwargs)

    # Метод для изменения места
    def transfer_place(self, new_place):
        self.place = new_place
        self.save()

    # Метод для обновления статуса
    def update_status(self, new_status):
        self.animal_status = new_status
        if self.is_archived():
            self.set_fixed_age()  # Фиксируем возраст при архивировании
        self.save()




class Maker(AnimalBase):
    
    plemstatus = models.CharField(max_length=200, verbose_name='Племенной статус')
    working_condition = models.CharField(max_length=200, verbose_name='Рабочее состояние')  # Текущий статус работы
    working_condition_date = models.DateField(verbose_name='Дата установки статуса', null=True, blank=True)  # Дата установки рабочего состояния

    class Meta:
        verbose_name = "Производитель"
        verbose_name_plural = "Производители"

    def __str__(self):
        return f"Производитель: {self.tag.tag_number}"

    # Метод для обновления рабочего состояния с датой
    def update_working_condition(self, new_condition):
        """
        Обновление рабочего состояния и установка даты.
        """
        self.working_condition = new_condition
        self.working_condition_date = date.today()  # Устанавливаем текущую дату
        self.save()

    # Переопределение метода save для проверки обновлений
    def save(self, *args, **kwargs):
        # Можно добавить любую логику перед сохранением, например проверку условий
        super(Maker, self).save(*args, **kwargs)

class Lambing(models.Model):
    ewe = models.ForeignKey('Sheep', on_delete=models.CASCADE, verbose_name='Овца (Мать)')
    maker = models.ForeignKey('Maker', on_delete=models.CASCADE, verbose_name='Производитель (Отец)')
    planned_lambing_date = models.DateField(verbose_name='Планируемая дата окота')
    actual_lambing_date = models.DateField(verbose_name='Фактическая дата окота', null=True, blank=True)
    number_of_lambs = models.IntegerField(verbose_name='Количество ягнят', null=True, blank=True)

    def __str__(self):
        return f"Окот {self.ewe.tag.tag_number} от производителя {self.maker.tag.tag_number}"

    class Meta:
        verbose_name = "Окот"
        verbose_name_plural = "Окоты"

    def calculate_planned_lambing_date(self):
        """
        Рассчитываем планируемую дату окота (155 дней от даты случки)
        """
        if not self.planned_lambing_date:
            self.planned_lambing_date = date.today() + timedelta(days=155)

    def save(self, *args, **kwargs):
        """
        Переопределение метода save, чтобы рассчитать планируемую дату окота.
        """
        if not self.planned_lambing_date:
            self.calculate_planned_lambing_date()
        super(Lambing, self).save(*args, **kwargs)

class Ram(AnimalBase):
    mother_tag = models.ForeignKey('Sheep', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Мать')
    father_tag = models.ForeignKey('Maker', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Отец')

    def __str__(self):
        return f"Баран {self.tag.tag_number}"


class Ewe(AnimalBase):
    mother_tag = models.ForeignKey('Sheep', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Мать')
    father_tag = models.ForeignKey('Maker', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Отец')

    def __str__(self):
        return f"Ярка {self.tag.tag_number}"

    # Метод для преобразования Ярки в Овцу после случки
    def to_sheep(self):
        sheep = Sheep.objects.create(
            tag=self.tag,
            animal_status=self.animal_status,
            birth_date=self.birth_date,
            weight_records=self.weight_records,
            veterinary_history=self.veterinary_history,
            place=self.place,
            mother_tag=self.mother_tag,
            father_tag=self.father_tag
        )
        self.delete()  # Удаляем объект ярки
        return sheep


class Sheep(AnimalBase):
    mother_tag = models.ForeignKey('Sheep', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Мать')
    father_tag = models.ForeignKey('Maker', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Отец')
    lambing_history = models.ManyToManyField('Lambing', related_name='sheep_lambings', verbose_name='История окотов')
    
    def __str__(self):
        return f"Овца {self.tag.tag_number}"

    # Метод для добавления нового окота
    def add_lambing(self, maker, actual_lambing_date, lambs_data):
        lambing = Lambing.objects.create(
            ewe=self,
            maker=maker,
            planned_lambing_date=self.planned_lambing_date,
            actual_lambing_date=actual_lambing_date,
            number_of_lambs=len(lambs_data)
        )
        self.lambing_history.add(lambing)  # Добавляем новый окот в историю
        
        # Добавляем ягнят (баранов и ярок)
        for lamb_data in lambs_data:
            if lamb_data['gender'] == 'male':
                Ram.objects.create(
                    tag=lamb_data['tag'],
                    birth_date=lambing.actual_lambing_date,
                    mother_tag=self,
                    father_tag=maker,
                    weight_records=lamb_data['weight']
                )
            else:
                Ewe.objects.create(
                    tag=lamb_data['tag'],
                    birth_date=lambing.actual_lambing_date,
                    mother_tag=self,
                    father_tag=maker,
                    weight_records=lamb_data['weight']
                )

        self.save()

    # Метод для установки планируемой даты окота
    def calculate_planned_lambing_date(self):
        """
        Рассчитываем планируемую дату окота (155 дней от даты случки).
        Если уже есть окот, то новая дата.
        """
        if not self.planned_lambing_date or self.is_new_lambing():
            self.planned_lambing_date = date.today() + timedelta(days=155)
        self.save()

    def is_new_lambing(self):
        """
        Проверяем, если уже есть новый окот.
        """
        return not self.lambing_history.filter(actual_lambing_date__isnull=True).exists()  # Проверяем, есть ли незаконченный окот
