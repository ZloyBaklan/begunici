from django.db import models

class Status(models.Model):
    status_type = models.CharField(max_length=200, verbose_name='Название статуса')
    date_of_status = models.DateField(verbose_name='Дата статуса')

    def __str__(self):
        return self.status_type
    
# Приложение animals

class Tag(models.Model):
    tag_number = models.CharField(max_length=100, unique=True, verbose_name='Бирка')
    animal_type = models.CharField(max_length=100, verbose_name='Тип животного')

    def __str__(self):
        return self.tag_number

class Place(models.Model):
    sheepfold = models.CharField(max_length=200, verbose_name='Овчарня')
    compartment = models.CharField(max_length=200, verbose_name='Отсек')

    def __str__(self):
        return f"{self.sheepfold} - {self.compartment}"


class Veterinary(models.Model):
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE, verbose_name='Бирка')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, verbose_name='Место')
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус')
    veterinary_care = models.ForeignKey('VeterinaryCare', on_delete=models.SET_NULL, null=True, verbose_name='Тип ветобработки')
    date_of_care = models.DateField(verbose_name='Дата обработки')
    medication = models.CharField(max_length=200, verbose_name='Препарат')

    def __str__(self):
        return f"Ветобработка {self.veterinary_care} для {self.tag.tag_number}"


class VeterinaryCare(models.Model):
    care_type = models.CharField(max_length=200, verbose_name='Тип ветобработки')

    def __str__(self):
        # Вернем все связанные с этим типом ветобработки записи и выведем последний препарат и дату обработки
        last_veterinary = Veterinary.objects.filter(veterinary_care=self).order_by('-date_of_care').first()
        if last_veterinary:
            return f"{self.care_type} - Препарат: {last_veterinary.medication}, Дата: {last_veterinary.date_of_care}"
        return self.care_type

class WeightRecord(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, verbose_name='Бирка')
    weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Вес (кг)')
    weight_date = models.DateField(verbose_name='Дата взвешивания')

    def __str__(self):
        return f"Вес: {self.weight} кг, Дата: {self.weight_date}"




