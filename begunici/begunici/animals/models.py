from django.db import models
from datetime import date
from veterinary.models import Tag, Status, Place, WeightRecord, VeterinaryCare


from dateutil.relativedelta import relativedelta

class AnimalBase(models.Model):
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, verbose_name='Бирка')
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    birth_date = models.DateField(verbose_name='Дата рождения')
    age = models.IntegerField(verbose_name='Возраст (в месяцах)', null=True, blank=True)
    
    class Meta:
        abstract = True  # Указываем, что это абстрактная модель

    # Метод для расчета возраста
    def calculate_age(self):
        if self.status and self.status.status_type not in ['Убыл', 'Убой', 'Продажа']:
            current_date = date.today()
            delta = relativedelta(current_date, self.birth_date)
            self.age = delta.years * 12 + delta.months  # Возраст в месяцах
            self.save()

    # Метод для фиксации возраста при смене статуса
    def set_fixed_age(self):
        if self.status and self.status.status_type in ['Убыл', 'Убой', 'Продажа']:
            current_date = date.today()
            delta = relativedelta(current_date, self.birth_date)
            self.age = delta.years * 12 + delta.months  # Фиксируем возраст в месяцах
            self.save()

    # Переопределение метода save для автообновления возраста
    def save(self, *args, **kwargs):
        if self.status and self.status.status_type in ['Убыл', 'Убой', 'Продажа']:
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
    weight_records = models.ForeignKey(WeightRecord, on_delete=models.SET_NULL, null=True, related_name='weight_records', verbose_name='История взвешиваний')
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
    weight_records = models.ForeignKey(WeightRecord, on_delete=models.SET_NULL, null=True, related_name='weight_records', verbose_name='История взвешиваний')
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
    weight_records = models.ForeignKey(WeightRecord, on_delete=models.SET_NULL, null=True, related_name='weight_records', verbose_name='История взвешиваний')
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
    weight_records = models.ForeignKey(WeightRecord, on_delete=models.SET_NULL, null=True, related_name='weight_records', verbose_name='История взвешиваний')
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

