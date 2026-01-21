from django.db import models
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from begunici.app_types.veterinary.vet_models import (
    Tag,
    Status,
    Veterinary,
    Place,
    WeightRecord,
    PlaceMovement,
    StatusHistory,
)


class AnimalBase(models.Model):
    tag = models.OneToOneField(
        Tag, on_delete=models.CASCADE, verbose_name="Бирка"
    )
    animal_status = models.ForeignKey(
        Status, on_delete=models.SET_NULL, null=True, verbose_name="Статус"
    )
    birth_date = models.DateField(verbose_name="Дата рождения", null=True, blank=True)
    age = models.DecimalField(
        verbose_name="Возраст (в месяцах)",
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
    )
    note = models.CharField(
        max_length=100, verbose_name="Примечание", null=True, blank=True
    )
    is_archived = models.BooleanField(default=False, verbose_name="В архиве")
    # Новые поля для родителей
    mother = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_children_mother",
        verbose_name="Мать",
    )
    father = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_children_father",
        verbose_name="Отец",
    )

    weight_records = models.ManyToManyField(
        WeightRecord, verbose_name="История взвешиваний", blank=True
    )

    veterinary_history = models.ManyToManyField(
        Veterinary, verbose_name="История ветобработок", blank=True
    )

    place = models.ForeignKey(
        Place, on_delete=models.SET_NULL, null=True, verbose_name="Место"
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
            try:
                current_date = timezone.now().date()
                
                # Убеждаемся, что birth_date - это объект date
                if isinstance(self.birth_date, str):
                    from datetime import datetime
                    birth_date = datetime.strptime(self.birth_date, '%Y-%m-%d').date()
                else:
                    birth_date = self.birth_date
                
                delta = relativedelta(current_date, birth_date)
                calculated_age = round(delta.years * 12 + delta.months + delta.days / 30, 1)
                self.age = calculated_age
            except (ValueError, TypeError) as e:
                # Если не удается вычислить возраст, устанавливаем None
                self.age = None

    def get_animal_type(self):
        """
        Возвращает тип животного для каждого наследника.
        Должен быть переопределён в дочерних классах.
        """
        raise NotImplementedError(
            "Метод get_animal_type должен быть переопределён в дочерних классах."
        )

    def save(self, *args, **kwargs):
        """
        Переопределяем сохранение, учитывая:
        1. Архивирование животного при изменении статуса.
        2. Обновление `animal_type` у `Tag`.
        3. Создание записей о перемещении (`PlaceMovement`).
        4. Создание записей об изменении статуса (`StatusHistory`).
        """
        is_new = self.pk is None  # Проверяем, создаётся ли новый объект
        old_place = None
        old_status = None

        # 🔹 Проверка на архивный статус
        if self.animal_status and self.animal_status.status_type in [
            "Убыл",
            "Убой",
            "Продажа",
        ]:
            self.is_archived = True
        else:
            self.is_archived = False
            self.calculate_age()

        # 🔹 Автоматическое заполнение `animal_type` у `Tag`
        if self.tag:
            self.tag.animal_type = self.get_animal_type()
            self.tag.save()

        # 🔹 Получаем старые значения до сохранения
        if not is_new:
            try:
                old_instance = self.__class__.objects.get(pk=self.pk)
                old_place = old_instance.place
                old_status = old_instance.animal_status
            except self.__class__.DoesNotExist:
                pass  # old_place и old_status останутся None

        # 🔹 Сохранение объекта
        super().save(*args, **kwargs)

        # 🔹 Создание записи о перемещении, если место изменилось
        if not is_new and self.place and old_place != self.place:
            PlaceMovement.objects.create(
                tag=self.tag, old_place=old_place, new_place=self.place
            )

        # 🔹 Создание записи в `StatusHistory`, если статус изменился
        if not is_new and self.animal_status and old_status != self.animal_status:
            StatusHistory.objects.create(
                tag=self.tag, old_status=old_status, new_status=self.animal_status
            )


class Maker(AnimalBase):
    plemstatus = models.CharField(max_length=200, verbose_name="Племенной статус")
    working_condition = models.CharField(
        max_length=200, verbose_name="Рабочее состояние"
    )  # Текущий статус работы
    working_condition_date = models.DateField(
        verbose_name="Дата установки статуса", null=True, blank=True
    )  # Дата установки рабочего состояния


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
        self.working_condition_date = (
            timezone.now().date()
        )  # Устанавливаем текущую дату
        self.save()

    def get_animal_type(self):
        return "Maker"

    def get_children(self):
        """
        Возвращает всех детей данного производителя (любого типа).
        """
        children = []
        # We need to query the base model to get all children, but since AnimalBase is abstract,
        # we query each concrete subclass.
        for model in [Ram, Ewe, Sheep, Maker]:
            children.extend(list(model.objects.filter(Q(father=self.tag) | Q(mother=self.tag))))

        # Sort children by birth date, for example
        children.sort(key=lambda x: x.birth_date or timezone.now().date(), reverse=True)
        return children


class Lambing(models.Model):
    # Мать может быть либо овцой, либо яркой
    sheep = models.ForeignKey(
        "Sheep", on_delete=models.CASCADE, verbose_name="Овца (Мать)", 
        null=True, blank=True, related_name="lambings"
    )
    ewe = models.ForeignKey(
        "Ewe", on_delete=models.CASCADE, verbose_name="Ярка (Мать)", 
        null=True, blank=True, related_name="lambings"
    )
    
    # Отец может быть либо производителем, либо бараном
    maker = models.ForeignKey(
        "Maker", on_delete=models.CASCADE, verbose_name="Производитель (Отец)",
        null=True, blank=True, related_name="lambings_as_father"
    )
    ram = models.ForeignKey(
        "Ram", on_delete=models.CASCADE, verbose_name="Баран (Отец)",
        null=True, blank=True, related_name="lambings_as_father"
    )
    
    start_date = models.DateField(verbose_name="Дата начала окота (случки)", default=timezone.now)
    planned_lambing_date = models.DateField(verbose_name="Планируемая дата окота", default=timezone.now)
    actual_lambing_date = models.DateField(
        verbose_name="Фактическая дата окота", null=True, blank=True
    )
    number_of_lambs = models.IntegerField(
        verbose_name="Количество ягнят", null=True, blank=True
    )
    note = models.TextField(
        verbose_name="Примечание", null=True, blank=True
    )
    is_active = models.BooleanField(default=True, verbose_name="Активный окот")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Дата создания")

    def __str__(self):
        mother = self.sheep or self.ewe
        father = self.maker or self.ram
        return f"Окот {mother.tag.tag_number} от {father.tag.tag_number}"

    class Meta:
        verbose_name = "Окот"
        verbose_name_plural = "Окоты"

    def get_mother(self):
        """Возвращает мать (овцу или ярку)"""
        return self.sheep or self.ewe
    
    def get_father(self):
        """Возвращает отца (производителя или барана)"""
        return self.maker or self.ram

    def get_mother_type(self):
        """Возвращает тип матери"""
        if self.sheep:
            return "Овца"
        elif self.ewe:
            return "Ярка"
        return None
    
    def get_father_type(self):
        """Возвращает тип отца"""
        if self.maker:
            return "Производитель"
        elif self.ram:
            return "Баран"
        return None

    def calculate_planned_lambing_date(self):
        """
        Рассчитываем планируемую дату окота (6 месяцев от даты начала)
        """
        if self.start_date:
            self.planned_lambing_date = self.start_date + relativedelta(months=6)

    def complete_lambing(self):
        """Завершить окот"""
        self.is_active = False
        self.save()

    def clean(self):
        """Валидация модели"""
        from django.core.exceptions import ValidationError
        
        # Проверяем, что указана только одна мать
        if not (self.sheep or self.ewe):
            raise ValidationError("Должна быть указана мать (овца или ярка)")
        if self.sheep and self.ewe:
            raise ValidationError("Нельзя указывать и овцу, и ярку одновременно")
            
        # Проверяем, что указан только один отец
        if not (self.maker or self.ram):
            raise ValidationError("Должен быть указан отец (производитель или баран)")
        if self.maker and self.ram:
            raise ValidationError("Нельзя указывать и производителя, и барана одновременно")
            
        # Проверяем, что у матери нет активного окота
        mother = self.get_mother()
        if mother and self.is_active:
            # Проверяем активные окоты в зависимости от типа матери
            if self.sheep:
                existing_active = Lambing.objects.filter(sheep=self.sheep, is_active=True)
            elif self.ewe:
                existing_active = Lambing.objects.filter(ewe=self.ewe, is_active=True)
            else:
                existing_active = Lambing.objects.none()
                
            existing_active = existing_active.exclude(pk=self.pk)
            if existing_active.exists():
                raise ValidationError(f"У {mother.tag.tag_number} уже есть активный окот")

    def save(self, *args, **kwargs):
        """
        Переопределение метода save, чтобы рассчитать планируемую дату окота.
        """
        if self.start_date and not self.planned_lambing_date:
            self.calculate_planned_lambing_date()
        super(Lambing, self).save(*args, **kwargs)


class Ram(AnimalBase):

    class Meta:
        verbose_name = "Баран"
        verbose_name_plural = "Бараны"

    def get_animal_type(self):
        return "Ram"

    def get_children(self):
        """
        Возвращает всех детей данного барана (любого типа).
        """
        children = []
        # Ищем среди всех типов животных
        for model in [Ram, Ewe, Sheep, Maker]:
            children.extend(list(model.objects.filter(Q(father=self.tag) | Q(mother=self.tag))))

        # Сортируем детей по дате рождения
        children.sort(key=lambda x: x.birth_date or timezone.now().date(), reverse=True)
        return children

    def __str__(self):
        return f"Баран {self.tag.tag_number}"


class Ewe(AnimalBase):

    class Meta:
        verbose_name = "Ярка"
        verbose_name_plural = "Ярки"

    def __str__(self):
        return f"Ярка {self.tag.tag_number}"

    def get_animal_type(self):
        return "Ewe"

    def get_children(self):
        """
        Возвращает всех детей данной ярки (любого типа).
        """
        children = []
        # Ищем среди всех типов животных
        for model in [Ram, Ewe, Sheep, Maker]:
            children.extend(list(model.objects.filter(Q(father=self.tag) | Q(mother=self.tag))))

        # Сортируем детей по дате рождения
        children.sort(key=lambda x: x.birth_date or timezone.now().date(), reverse=True)
        return children

    # Метод для преобразования Ярки в Овцу после случки
    def to_sheep(self):
        # Создаем новую овцу с теми же данными
        sheep = Sheep.objects.create(
            tag=self.tag,
            animal_status=self.animal_status,
            birth_date=self.birth_date,
            place=self.place,
            mother=self.mother,
            father=self.father,
            note=self.note,
        )
        
        # Переносим записи о весе (обновляем tag в записях)
        from begunici.app_types.veterinary.vet_models import WeightRecord, Veterinary
        WeightRecord.objects.filter(tag=self.tag).update(tag=self.tag)
        Veterinary.objects.filter(tag=self.tag).update(tag=self.tag)
        
        # Удаляем ярку
        self.delete()
        return sheep


class Sheep(AnimalBase):
    planned_lambing_date = models.DateField(
        verbose_name="Планируемая дата окота", null=True, blank=True
    )
    lambing_history = models.ManyToManyField(
        "Lambing",
        related_name="sheep_lambings",
        blank=True,
        verbose_name="История окотов",
    )

    class Meta:
        verbose_name = "Овца"
        verbose_name_plural = "Овцы"

    def __str__(self):
        return f"Овца {self.tag.tag_number}"

    def get_animal_type(self):
        return "Sheep"

    def get_children(self):
        """
        Возвращает всех детей данной овцы (любого типа).
        """
        children = []
        # Ищем среди всех типов животных
        for model in [Ram, Ewe, Sheep, Maker]:
            children.extend(list(model.objects.filter(Q(father=self.tag) | Q(mother=self.tag))))

        # Сортируем детей по дате рождения
        children.sort(key=lambda x: x.birth_date or timezone.now().date(), reverse=True)
        return children

    # Метод для добавления нового окота
    def add_lambing(self, maker, actual_lambing_date, lambs_data):
        lambing = Lambing.objects.create(
            ewe=self,
            maker=maker,
            planned_lambing_date=self.planned_lambing_date,
            actual_lambing_date=actual_lambing_date,
            number_of_lambs=len(lambs_data),
        )
        self.lambing_history.add(lambing)  # Добавляем новый окот в историю

        # Добавляем ягнят (баранов и ярок)
        for lamb_data in lambs_data:
            if lamb_data["gender"] == "male":
                Ram.objects.create(
                    tag=lamb_data["tag"],
                    birth_date=lambing.actual_lambing_date,
                    mother=self.tag,
                    father=maker.tag,
                )
            else:
                Ewe.objects.create(
                    tag=lamb_data["tag"],
                    birth_date=lambing.actual_lambing_date,
                    mother=self.tag,
                    father=maker.tag,
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
        return not self.lambing_history.filter(
            actual_lambing_date__isnull=True
        ).exists()  # Проверяем, есть ли незаконченный окот
