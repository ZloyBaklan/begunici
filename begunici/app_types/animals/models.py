from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.models import User
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
        max_length=300, verbose_name="Примечание", null=True, blank=True
    )
    rshn_tag = models.CharField(
        max_length=50, 
        verbose_name="Бирка РСХН", 
        null=True, 
        blank=True,
        unique=True,
        help_text="Уникальный номер бирки РСХН (необязательно)"
    )
    date_otbivka = models.DateField(
        verbose_name="Дата отбивки",
        null=True,
        blank=True,
        help_text="Дата отбивки животного (необязательно)"
    )
    is_archived = models.BooleanField(default=False, verbose_name="В архиве")
    # Поля для родителей (текстовые поля с номерами бирок)
    mother = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Мать (номер бирки)",
        help_text="Номер бирки матери (буквы и цифры без пробелов)"
    )
    father = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Отец (номер бирки)",
        help_text="Номер бирки отца (буквы и цифры без пробелов)"
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

    def get_age_display(self):
        """
        Возвращает возраст в формате 'X мес. (Y сут)'
        """
        if not self.birth_date:
            return None
            
        try:
            current_date = timezone.now().date()
            
            # Убеждаемся, что birth_date - это объект date
            if isinstance(self.birth_date, str):
                from datetime import datetime
                birth_date = datetime.strptime(self.birth_date, '%Y-%m-%d').date()
            else:
                birth_date = self.birth_date
            
            delta = relativedelta(current_date, birth_date)
            
            # Рассчитываем полные месяцы
            total_months = delta.years * 12 + delta.months
            
            # Рассчитываем дни (округляем до целых)
            days = round(delta.days)
            
            if total_months == 0 and days == 0:
                return "0 мес."
            elif total_months == 0:
                return f"{days} сут."
            elif days == 0:
                return f"{total_months} мес."
            else:
                return f"{total_months} мес. ({days} сут.)"
                
        except (ValueError, TypeError):
            return None

    def get_animal_type(self):
        """
        Возвращает тип животного для каждого наследника.
        Должен быть переопределён в дочерних классах.
        """
        raise NotImplementedError(
            "Метод get_animal_type должен быть переопределён в дочерних классах."
        )

    def get_mother_tag(self):
        """Получить Tag объект матери, если он существует в БД"""
        if not self.mother:
            return None
        try:
            return Tag.objects.get(tag_number=self.mother)
        except Tag.DoesNotExist:
            return None

    def get_father_tag(self):
        """Получить Tag объект отца, если он существует в БД"""
        if not self.father:
            return None
        try:
            return Tag.objects.get(tag_number=self.father)
        except Tag.DoesNotExist:
            return None

    def get_mother_display(self):
        """Получить отображение матери (ссылка или текст)"""
        if not self.mother:
            return None
        
        mother_tag = self.get_mother_tag()
        if mother_tag:
            return {
                'tag_number': self.mother,
                'has_link': True,
                'tag_obj': mother_tag
            }
        else:
            return {
                'tag_number': self.mother,
                'has_link': False,
                'tag_obj': None
            }

    def get_father_display(self):
        """Получить отображение отца (ссылка или текст)"""
        if not self.father:
            return None
        
        father_tag = self.get_father_tag()
        if father_tag:
            return {
                'tag_number': self.father,
                'has_link': True,
                'tag_obj': father_tag
            }
        else:
            return {
                'tag_number': self.father,
                'has_link': False,
                'tag_obj': None
            }

    def clean(self):
        """Валидация полей модели"""
        super().clean()
        
        # Валидация номера бирки матери
        if self.mother:
            self.mother = self.mother.strip()
            if ' ' in self.mother:
                from django.core.exceptions import ValidationError
                raise ValidationError({'mother': 'Номер бирки матери не должен содержать пробелы'})
        
        # Валидация номера бирки отца
        if self.father:
            self.father = self.father.strip()
            if ' ' in self.father:
                from django.core.exceptions import ValidationError
                raise ValidationError({'father': 'Номер бирки отца не должен содержать пробелы'})

    def save(self, *args, **kwargs):
        """
        Переопределяем сохранение, учитывая:
        1. Архивирование животного при изменении статуса.
        2. Обновление `animal_type` у `Tag`.
        3. Создание записей о перемещении (`PlaceMovement`).
        4. Создание записей об изменении статуса (`StatusHistory`).
        """
        print(f"Сохранение животного {self.tag.tag_number if self.tag else 'без бирки'}")
        is_new = self.pk is None  # Проверяем, создаётся ли новый объект
        old_place = None
        old_status = None
        
        # Параметр для пропуска создания StatusHistory (используется в сериализаторе)
        skip_status_history = kwargs.pop('skip_status_history', False)

        # 🔹 Проверка на архивный статус
        if self.animal_status and self.animal_status.status_type in [
            "Убыл",
            "Убой", 
            "Продажа на мясо",
            "Продажа на племя",
        ]:
            self.is_archived = True
        else:
            self.is_archived = False
        
        # 🔹 Вычисляем возраст независимо от статуса архивирования
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

        # 🔹 Создание записи в `StatusHistory`, если статус изменился (только если не пропускаем)
        if not is_new and self.animal_status and old_status != self.animal_status and not skip_status_history:
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
    
    # Поля для матери, которой нет в БД (для импорта исторических данных)
    mother_tag_text = models.CharField(
        max_length=50, verbose_name="Бирка матери (текст)", 
        null=True, blank=True, help_text="Используется когда матери нет в БД"
    )
    mother_type_text = models.CharField(
        max_length=20, verbose_name="Тип матери (текст)", 
        null=True, blank=True, help_text="Овца/Ярка для матерей не в БД"
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
        elif self.mother_type_text:
            return self.mother_type_text
        return None
    
    def get_mother_tag(self):
        """Возвращает бирку матери"""
        if self.sheep:
            return self.sheep.tag.tag_number
        elif self.ewe:
            return self.ewe.tag.tag_number
        elif self.mother_tag_text:
            return self.mother_tag_text
        return None
    
    def get_mother_display_info(self):
        """Возвращает информацию о матери для отображения"""
        if self.sheep or self.ewe:
            mother = self.get_mother()
            return {
                'tag': mother.tag.tag_number,
                'type': self.get_mother_type(),
                'found': True
            }
        elif self.mother_tag_text:
            return {
                'tag': self.mother_tag_text,
                'type': self.mother_type_text or 'Неизвестно',
                'found': False
            }
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
        Рассчитываем планируемую дату окота (150 дней от даты начала)
        """
        if self.start_date:
            self.planned_lambing_date = self.start_date + timedelta(days=150)

    def complete_lambing(self):
        """Завершить окот"""
        # Если мать - ярка, преобразуем её в овцу
        mother = self.get_mother()
        if mother and self.get_mother_type() == "Ярка":
            # Преобразуем ярку в овцу
            sheep = mother.to_sheep()
            # Обновляем связь окота с новой овцой
            self.sheep = sheep
            self.ewe = None
        
        self.is_active = False
        self.save()

    def clean(self):
        """Валидация модели"""
        from django.core.exceptions import ValidationError
        
        # Проверяем, что указана мать (либо объект, либо текстовые поля)
        has_mother_object = bool(self.sheep or self.ewe)
        has_mother_text = bool(self.mother_tag_text)
        
        if not (has_mother_object or has_mother_text):
            raise ValidationError("Должна быть указана мать (объект или текстовые данные)")
        
        if has_mother_object and has_mother_text:
            raise ValidationError("Нельзя указывать и объект матери, и текстовые данные одновременно")
            
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
        Переопределение метода save для автоматического изменения статуса матери
        """
        is_new = self.pk is None
        
        if is_new and self.is_active:
            # При создании нового активного окота меняем статус матери на "Окот"
            mother = self.get_mother()
            if mother:
                try:
                    # Ищем статус "Окот"
                    okot_status = Status.objects.filter(status_type__iexact="Окот").first()
                    if okot_status:
                        # Устанавливаем статус "Окот"
                        mother.animal_status = okot_status
                        mother.save()
                except Exception as e:
                    print(f"Ошибка при изменении статуса на 'Окот': {e}")
        
        # Рассчитываем планируемую дату окота если нужно
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
        # Создаем новую овцу с ВСЕМИ данными из AnimalBase
        sheep = Sheep.objects.create(
            tag=self.tag,
            animal_status=self.animal_status,
            birth_date=self.birth_date,
            age=self.age,  # ДОБАВЛЕНО: возраст
            note=self.note,
            rshn_tag=self.rshn_tag,  # ДОБАВЛЕНО: бирка РСХН
            date_otbivka=self.date_otbivka,  # ДОБАВЛЕНО: дата отбивки
            is_archived=self.is_archived,  # ДОБАВЛЕНО: статус архива
            mother=self.mother,
            father=self.father,
            place=self.place,
        )
        
        # Переносим ManyToMany связи
        from begunici.app_types.veterinary.vet_models import WeightRecord, Veterinary
        
        # Переносим записи о весе через ManyToMany связь
        for weight_record in self.weight_records.all():
            sheep.weight_records.add(weight_record)
        
        # Переносим ветеринарную историю через ManyToMany связь
        for vet_record in self.veterinary_history.all():
            sheep.veterinary_history.add(vet_record)
        
        # ВАЖНО: Переносим ВСЕ окоты ярки на новую овцу
        from begunici.app_types.animals.models import Lambing
        all_ewe_lambings = Lambing.objects.filter(ewe=self)
        for lambing in all_ewe_lambings:
            lambing.sheep = sheep
            lambing.ewe = None
            lambing.save()
        
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
        Рассчитываем планируемую дату окота (150 дней от даты случки).
        Если уже есть окот, то новая дата.
        """
        if not self.planned_lambing_date or self.is_new_lambing():
            self.planned_lambing_date = timezone.now().date() + timedelta(days=150)
        self.save()

    def is_new_lambing(self):
        """
        Проверяем, если уже есть новый окот.
        """
        return not self.lambing_history.filter(
            actual_lambing_date__isnull=True
        ).exists()  # Проверяем, есть ли незаконченный окот


class CalendarNote(models.Model):
    """
    Модель для заметок в календаре
    """
    date = models.DateField(verbose_name="Дата заметки")
    text = models.TextField(verbose_name="Текст заметки")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Заметка календаря"
        verbose_name_plural = "Заметки календаря"
        ordering = ['-date']

    def __str__(self):
        return f"Заметка на {self.date}: {self.text[:200]}..."

    def get_formatted_text(self):
        """
        Преобразует текст заметки, заменяя бирки на HTML-ссылки и статусы на цветные элементы
        """
        import re
        
        formatted_text = self.text
        
        # 1. Обрабатываем бирки
        # Паттерн для бирок: строки из букв и цифр, содержащие и то, и другое
        tag_pattern = r'\b([А-Яа-яA-Za-z0-9]{2,})\b'
        
        def replace_tag_link(match):
            tag_text = match.group(1)
            
            # Пропускаем слишком короткие совпадения (менее 2 символов)
            if len(tag_text) < 2:
                return tag_text
            
            # Пропускаем слишком длинные строки (вероятно, обычные слова)
            if len(tag_text) > 10:
                return tag_text
            
            # Проверяем, что строка похожа на бирку:
            # - содержит цифры ИЛИ
            # - короткая (до 5 символов) ИЛИ  
            # - содержит заглавные буквы
            import re
            has_digit = bool(re.search(r'[0-9]', tag_text))
            has_uppercase = bool(re.search(r'[А-ЯA-Z]', tag_text))
            is_short = len(tag_text) <= 5
            
            if not (has_digit or has_uppercase or is_short):
                return tag_text
            
            try:
                from begunici.app_types.veterinary.vet_models import Tag
                from django.urls import reverse
                
                # Проверяем, существует ли такая бирка (точное совпадение)
                tag_obj = Tag.objects.filter(tag_number__iexact=tag_text).first()
                if tag_obj:
                    # Определяем тип животного по animal_type
                    url_map = {
                        'Maker': 'animals:maker-detail',
                        'Ram': 'animals:ram-detail', 
                        'Ewe': 'animals:ewe-detail',
                        'Sheep': 'animals:sheep-detail'
                    }
                    
                    if tag_obj.animal_type in url_map:
                        url = reverse(url_map[tag_obj.animal_type], kwargs={'tag_number': tag_obj.tag_number})
                        return f'<a href="{url}" style="color: #007bff; text-decoration: underline; font-weight: bold;">{tag_text}</a>'
                
                # Если бирка не найдена, возвращаем обычный текст
                return tag_text
            except Exception as e:
                print(f"Ошибка обработки бирки {tag_text}: {e}")
                return tag_text
        
        formatted_text = re.sub(tag_pattern, replace_tag_link, formatted_text)
        
        # 2. Обрабатываем статусы
        try:
            from begunici.app_types.veterinary.vet_models import Status
            
            statuses = Status.objects.all()
            for status_obj in statuses:
                # Создаем паттерн для поиска статуса (частичное совпадение, без учета регистра)
                # Используем word boundary для точного поиска слов
                status_pattern = re.compile(r'\b' + re.escape(status_obj.status_type) + r'\b', re.IGNORECASE)
                
                def replace_status(match):
                    status_text = match.group(0)
                    color = status_obj.color if status_obj.color else '#000000'
                    return f'<span style="border: 1px solid {color}; padding: 2px 4px; border-radius: 3px; font-weight: bold; display: inline-block; background-color: rgba({self._hex_to_rgb(color)}, 0.1);">{status_text}</span>'
                
                formatted_text = status_pattern.sub(replace_status, formatted_text)
        except Exception as e:
            print(f"Ошибка обработки статусов: {e}")
        
        return formatted_text

    def _hex_to_rgb(self, hex_color):
        """
        Конвертирует HEX цвет в RGB для прозрачного фона
        """
        try:
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return f"{r}, {g}, {b}"
            return "0, 0, 0"
        except:
            return "0, 0, 0"





