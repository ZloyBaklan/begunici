from django.db import models

class Place(models.Model):
    sheepfold = models.CharField(max_length=200, verbose_name='Овчарня')
    compartment = models.CharField(max_length=200, verbose_name='Отсек')

    def __str__(self):
        return f"{self.sheepfold} - {self.compartment}"


class Maker(models.Model):
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, verbose_name='Бирка')
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    age = models.IntegerField(verbose_name='Возраст')
    plemstatus = models.CharField(max_length=200, verbose_name='Племенной статус')
    last_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Последний вес')
    last_weight_date = models.DateField(verbose_name='Дата последнего взвешивания')
    working_condition = models.CharField(max_length=200, verbose_name='Рабочее состояние')
    veterinary_care = models.CharField(max_length=200, verbose_name='Вет обработка')

    def __str__(self):
        return f"Maker: {self.tag.tag_number}"



class Ram(models.Model):
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, verbose_name='Бирка')
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    birth_date = models.DateField(verbose_name='Дата рождения')
    age = models.IntegerField(verbose_name='Возраст')
    mother_tag = models.CharField(max_length=200, verbose_name='Бирка матери')
    father_tag = models.CharField(max_length=200, verbose_name='Бирка отца')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    replace_date = models.DateField(verbose_name='Дата перевода')
    last_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Последний вес')
    last_weight_date = models.DateField(verbose_name='Дата последнего взвешивания')
    first_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Первый вес')
    first_weight_date = models.DateField(verbose_name='Дата первого взвешивания')
    veterinary_care = models.CharField(max_length=200, verbose_name='Вет обработка')

    def __str__(self):
        return f"Ram: {self.tag.tag_number}"



class Ewe(models.Model):
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, verbose_name='Бирка')
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    birth_date = models.DateField(verbose_name='Дата рождения')
    age = models.IntegerField(verbose_name='Возраст')
    mother_tag = models.CharField(max_length=200, verbose_name='Бирка матери')
    father_tag = models.CharField(max_length=200, verbose_name='Бирка отца')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    replace_date = models.DateField(verbose_name='Дата перевода')
    last_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Последний вес')
    last_weight_date = models.DateField(verbose_name='Дата последнего взвешивания')
    first_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Первый вес')
    first_weight_date = models.DateField(verbose_name='Дата первого взвешивания')
    veterinary_care = models.CharField(max_length=200, verbose_name='Вет обработка')

    def __str__(self):
        return f"Ewe: {self.tag.tag_number}"


    
class Sheep(models.Model):
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, verbose_name='Бирка')
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    birth_date = models.DateField(verbose_name='Дата рождения')
    age = models.IntegerField(verbose_name='Возраст')
    mother_tag = models.CharField(max_length=200, verbose_name='Бирка матери')
    father_tag = models.CharField(max_length=200, verbose_name='Бирка отца')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    replace_date = models.DateField(verbose_name='Дата перевода')
    last_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Последний вес')
    last_weight_date = models.DateField(verbose_name='Дата последнего взвешивания')
    first_weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Первый вес')
    first_weight_date = models.DateField(verbose_name='Дата первого взвешивания')
    veterinary_care = models.CharField(max_length=200, verbose_name='Вет обработка')
    maker_tag = models.CharField(max_length=200, verbose_name='Производитель на окот')
    planned_salary = models.DateField(verbose_name='Планируемая дата окота')
    fact_salary = models.DateField(verbose_name='Фактическая дата окота')
    lamb_count = models.IntegerField(verbose_name='Число ягнят')
    lamb_tag = models.CharField(max_length=200, verbose_name='Бирки ягнят')

    def __str__(self):
        return f"Sheep: {self.tag.tag_number}"

