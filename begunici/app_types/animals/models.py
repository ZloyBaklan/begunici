from django.db import models
from datetime import date, timedelta
from begunici.app_types.veterinary.models import Tag, Status, Place, WeightRecord, VeterinaryCare


from dateutil.relativedelta import relativedelta

class AnimalBase(models.Model):
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, verbose_name='Бирка')
    animal_status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    birth_date = models.DateField(verbose_name='Дата рождения')
    age = models.IntegerField(verbose_name='Возраст (в месяцах)', null=True, blank=True)
    weight_records = models.ForeignKey(
        WeightRecord, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='%(class)s_weight_records',  # Уникальный related_name для каждой модели
        verbose_name='История взвешиваний'
    )

    class Meta:
        abstract = True  # Указываем, что это абстрактная модель

    # Метод для расчета возраста
    def calculate_age(self):
        if self.animal_status and self.animal_status.status_type not in ['Убыл', 'Убой', 'Продажа']:
            current_date = date.today()
            delta = relativedelta(current_date, self.birth_date)
            self.age = delta.years * 12 + delta.months  # Возраст в месяцах
            self.save()

    # Метод для фиксации возраста при смене статуса
    def set_fixed_age(self):
        if self.animal_status and self.animal_status.status_type in ['Убыл', 'Убой', 'Продажа']:
            current_date = date.today()
            delta = relativedelta(current_date, self.birth_date)
            self.age = delta.years * 12 + delta.months  # Фиксируем возраст в месяцах
            self.save()

    # Переопределение метода save для автообновления возраста
    def save(self, *args, **kwargs):
        if self.animal_status and self.animal_status.status_type in ['Убыл', 'Убой', 'Продажа']:
            self.set_fixed_age()  # Фиксируем возраст
        else:
            self.calculate_age()  # Рассчитываем возраст
        super(AnimalBase, self).save(*args, **kwargs)




class Maker(AnimalBase):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    plemstatus = models.CharField(max_length=200, verbose_name='Племенной статус')
    # Последний вес
    last_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Последний вес')
    last_weight_date = models.DateField(verbose_name='Дата последнего взвешивания')
    # Связь с историей взвешиваний
    # weight_records = models.ForeignKey(WeightRecord, on_delete=models.SET_NULL, null=True, related_name='maker_weight_records', verbose_name='История взвешиваний')
    working_condition = models.CharField(max_length=200, verbose_name='Рабочее состояние')
    veterinary_care = models.ForeignKey(VeterinaryCare, on_delete=models.SET_NULL, null=True, verbose_name='Последняя ветобработка')
    
    def __str__(self):
        return f"Maker: {self.tag.tag_number}"



class Ram(AnimalBase):  # Наследуем от AnimalBase
    mother_tag = models.CharField(max_length=200, verbose_name='Бирка матери')
    father_tag = models.CharField(max_length=200, verbose_name='Бирка отца')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    replace_date = models.DateField(verbose_name='Дата перевода')
    # Последний вес
    last_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Последний вес')
    last_weight_date = models.DateField(verbose_name='Дата последнего взвешивания')
    # Связь с историей взвешиваний
    # weight_records = models.ForeignKey(WeightRecord, on_delete=models.SET_NULL, null=True, related_name='maker_weight_records', verbose_name='История взвешиваний')
    veterinary_care = models.ForeignKey(VeterinaryCare, on_delete=models.SET_NULL, null=True, verbose_name='Последняя ветобработка')
    
    def __str__(self):
        return f"Ram: {self.tag.tag_number}"



class Ewe(AnimalBase):
    mother_tag = models.CharField(max_length=200, verbose_name='Бирка матери')
    father_tag = models.CharField(max_length=200, verbose_name='Бирка отца')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    replace_date = models.DateField(verbose_name='Дата перевода')
    # Последний вес
    last_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Последний вес')
    last_weight_date = models.DateField(verbose_name='Дата последнего взвешивания')
    # Связь с историей взвешиваний
    # weight_records = models.ForeignKey(WeightRecord, on_delete=models.SET_NULL, null=True, related_name='maker_weight_records', verbose_name='История взвешиваний')
    veterinary_care = models.ForeignKey(VeterinaryCare, on_delete=models.SET_NULL, null=True, verbose_name='Последняя ветобработка')
    
    def __str__(self):
        return f"Ewe: {self.tag.tag_number}"


    
class Sheep(AnimalBase):
    mother_tag = models.CharField(max_length=200, verbose_name='Бирка матери')
    father_tag = models.CharField(max_length=200, verbose_name='Бирка отца')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    replace_date = models.DateField(verbose_name='Дата перевода')
    # Последний вес
    last_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Последний вес')
    last_weight_date = models.DateField(verbose_name='Дата последнего взвешивания')
    # Связь с историей взвешиваний
    # weight_records = models.ForeignKey(WeightRecord, on_delete=models.SET_NULL, null=True, related_name='maker_weight_records', verbose_name='История взвешиваний')
    veterinary_care = models.ForeignKey(VeterinaryCare, on_delete=models.SET_NULL, null=True, verbose_name='Последняя ветобработка')
    maker_tag = models.CharField(max_length=200, verbose_name='Производитель на окот')
    planned_salary = models.DateField(verbose_name='Планируемая дата окота')
    fact_salary = models.DateField(verbose_name='Фактическая дата окота')
    lamb_count = models.IntegerField(verbose_name='Число ягнят')
    lamb_tag = models.CharField(max_length=200, verbose_name='Бирки ягнят')

    def __str__(self):
        return f"Sheep: {self.tag.tag_number}"
    
class Lamb(AnimalBase):
    weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Вес (кг)')
    gender = models.CharField(max_length=10, choices=[('М', 'Мужской'), ('Ж', 'Женский')], verbose_name='Пол')
    def __str__(self):
        return f"{self.tag.tag_number} - Пол: {self.gender}, Вес: {self.weight} кг"


class Lambing(models.Model):
    sheep = models.ForeignKey(Sheep, on_delete=models.CASCADE, verbose_name='Овца')
    
    # Дата постановки под барана
    mating_date = models.DateField(verbose_name='Дата постановки под барана')
    
    # Ориентировочная дата окота (плюс 155 дней)
    estimated_lambing_date = models.DateField(verbose_name='Ориентировочная дата окота')
    
    # Фактическая дата окота
    actual_lambing_date = models.DateField(verbose_name='Фактическая дата окота', null=True, blank=True)
    
    # Число ягнят
    lamb_count = models.IntegerField(verbose_name='Число ягнят')
    
    # Ягнята (связь с моделью Lamb)
    lambs = models.ManyToManyField(Lamb, verbose_name='Ягнята')
    
    # Производитель (Maker)
    maker = models.ForeignKey(Maker, on_delete=models.CASCADE, verbose_name='Производитель', null=True, blank=True)

    def save(self, *args, **kwargs):
        # При сохранении автоматически вычисляем ориентировочную дату окота
        if not self.estimated_lambing_date:
            self.estimated_lambing_date = self.mating_date + timedelta(days=155)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Окот овцы {self.sheep.tag.tag_number} от производителя {self.maker.tag.tag_number} - Число ягнят: {self.lamb_count}"