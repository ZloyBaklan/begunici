from django.db import models
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from begunici.app_types.veterinary.vet_models import Tag, Status, Veterinary, Place, WeightRecord, PlaceMovement, StatusHistory


from dateutil.relativedelta import relativedelta

class AnimalBase(models.Model):
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, verbose_name='Бирка', unique=True)
    animal_status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    birth_date = models.DateField(verbose_name='Дата рождения', null=True, blank=True)
    age = models.DecimalField(verbose_name='Возраст (в месяцах)', max_digits=5, decimal_places=1, null=True, blank=True)
    note = models.CharField(max_length=100, verbose_name='Примечание', null=True, blank=True)
    is_archived = models.BooleanField(default=False, verbose_name='В архиве')
    # Новые поля для родителей
    mother = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children_mother',
        verbose_name='Мать'
    )
    father = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children_father',
        verbose_name='Отец'
    )

    weight_records = models.ManyToManyField(
        WeightRecord,
        verbose_name='История взвешиваний',
        blank=True
    )

    veterinary_history = models.ManyToManyField(
        Veterinary,
        verbose_name='История ветобработок',
        blank=True
    )

    place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Место'
    )
    
    class Meta:
        abstract = True
    
    # Автоматическое добавление place_movements через related_name
    @property
    def place_movements(self):
        return self.tag.place_movements.all()
    
    @property
    def status_history(self):
        return self.tag.status_history.all()

    # Расчет возраста
    def calculate_age(self):
        if self.birth_date:
            current_date = timezone.now().date()
            delta = relativedelta(current_date, self.birth_date)
            calculated_age = round(delta.years * 12 + delta.months + delta.days / 30, 1)
            self.age = calculated_age
    def get_animal_type(self):
        """
        Возвращает тип животного для каждого наследника.
        Должен быть переопределён в дочерних классах.
        """
        raise NotImplementedError("Метод get_animal_type должен быть переопределён в дочерних классах.")

    def save(self, *args, **kwargs):
        if self.animal_status and self.animal_status.status_type in ['Убыл', 'Убой', 'Продажа']:
            self.is_archived = True
        else:
            self.is_archived = False
            self.calculate_age()
        
        # Автоматическое заполнение animal_type в Tag
        if self.tag:
            self.tag.animal_type = self.get_animal_type()  # Используем метод get_animal_type
            self.tag.save()
        
        # Обработка изменений места (создание записи о перемещении)
        if self.place and self.pk:
            old_place = self.__class__.objects.get(pk=self.pk).place
            print(f"Старое место: {old_place}, Новое место: {self.place}")
            if old_place != self.place:
                movement = PlaceMovement.objects.create(
                    tag=self.tag,
                    old_place=old_place,
                    new_place=self.place
                )
                print(f"Создано перемещение: {movement}")

        #  Обработка изменений статуса
        if self.animal_status and self.pk:
            old_status = self.__class__.objects.get(pk=self.pk).animal_status
            if old_status != self.animal_status:
                StatusHistory.objects.create(
                    tag=self.tag,
                    old_status=old_status if old_status else None,
                    new_status=self.animal_status
                )

        super(AnimalBase, self).save(*args, **kwargs)
  
    




class Maker(AnimalBase):
    plemstatus = models.CharField(max_length=200, verbose_name='Племенной статус')
    working_condition = models.CharField(max_length=200, verbose_name='Рабочее состояние')  # Текущий статус работы
    working_condition_date = models.DateField(verbose_name='Дата установки статуса', null=True, blank=True)  # Дата установки рабочего состояния

    mother = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maker_children_mother',
        verbose_name='Мать'
    )
    father = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maker_children_father',
        verbose_name='Отец'
    )

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
        self.working_condition_date = timezone.now().date()  # Устанавливаем текущую дату
        self.save()
    
    def get_animal_type(self):
        return "Maker"
    
    def get_children(self):
        """
        Возвращает всех детей данного производителя.
        """
        return Maker.objects.filter(Q(mother=self.tag) | Q(father=self.tag))



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
            self.planned_lambing_date = timezone.now().date() + timedelta(days=155)

    def save(self, *args, **kwargs):
        """
        Переопределение метода save, чтобы рассчитать планируемую дату окота.
        """
        if not self.planned_lambing_date:
            self.calculate_planned_lambing_date()
        super(Lambing, self).save(*args, **kwargs)

class Ram(AnimalBase):
    mother = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children_mother_ram',
        verbose_name='Мать'
    )
    father = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children_father_ram',
        verbose_name='Отец'
    )
    def get_animal_type(self):
        return "Ram"

    # Другие поля Ram

    def __str__(self):
        return f"Баран {self.tag.tag_number}"


class Ewe(AnimalBase):
    mother = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children_mother_ewe',
        verbose_name='Мать'
    )
    father = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children_father_ewe',
        verbose_name='Отец'
    )

    def __str__(self):
        return f"Ярка {self.tag.tag_number}"
    
    def get_animal_type(self):
        return "Ewe"

    # Метод для преобразования Ярки в Овцу после случки
    def to_sheep(self):
        sheep = Sheep.objects.create(
            tag=self.tag,
            animal_status=self.animal_status,
            birth_date=self.birth_date,
            place=self.place,
            mother=self.mother,
            father=self.father
        )
        sheep.weight_records.set(self.weight_records.all())
        sheep.veterinary_history.set(self.veterinary_history.all())
        self.delete()
        return sheep


class Sheep(AnimalBase):
    mother = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children_mother_sheep',
        verbose_name='Мать'
    )
    father = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children_father_sheep',
        verbose_name='Отец'
    )
    lambing_history = models.ManyToManyField('Lambing', related_name='sheep_lambings', blank=True, verbose_name='История окотов')
    
    def __str__(self):
        return f"Овца {self.tag.tag_number}"
    
    def get_animal_type(self):
        return "Sheep"

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
                )
            else:
                Ewe.objects.create(
                    tag=lamb_data['tag'],
                    birth_date=lambing.actual_lambing_date,
                    mother_tag=self,
                    father_tag=maker,
                )

        self.save()

    # Метод для установки планируемой даты окота
    def calculate_planned_lambing_date(self):
        """
        Рассчитываем планируемую дату окота (155 дней от даты случки).
        Если уже есть окот, то новая дата.
        """
        if not self.planned_lambing_date or self.is_new_lambing():
            self.planned_lambing_date = timezone.now().date() + timedelta(days=155)
        self.save()

    def is_new_lambing(self):
        """
        Проверяем, если уже есть новый окот.
        """
        return not self.lambing_history.filter(actual_lambing_date__isnull=True).exists()  # Проверяем, есть ли незаконченный окот
    
    def get_children(self):
        """
        Возвращает список детей производителя.
        """
        return Sheep.objects.filter(models.Q(mother=self.tag) | models.Q(father=self.tag))
    
