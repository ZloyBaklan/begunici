from django.db import models

class Veterinary(models.Model):
    tag = models.TextField(verbose_name='Описание',
                            max_length=1000)  
    place = models.ManyToManyField(Tag, related_name='tags',
                                  verbose_name='Хэштег')
    status = models.TextField(verbose_name='Описание',
                            max_length=1000)
    veterinary_care = models.TextField(verbose_name='Описание',
                            max_length=1000)
    date_of_care = models.TextField(verbose_name='Описание',
                            max_length=1000)
    medication = models.TextField(verbose_name='Описание',
                            max_length=1000)

class Status(models.Model):
    status_type = models.TextField(verbose_name='Название статуса',
                            max_length=1000)  
