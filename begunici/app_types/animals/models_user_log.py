from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import pytz


class UserActionLog(models.Model):
    """
    Модель для логирования всех действий пользователей
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Пользователь"
    )
    action_type = models.CharField(
        max_length=50,
        verbose_name="Тип действия"
    )
    object_type = models.CharField(
        max_length=50,
        verbose_name="Тип объекта",
        null=True,
        blank=True
    )
    object_id = models.CharField(
        max_length=100,
        verbose_name="ID объекта",
        null=True,
        blank=True
    )
    description = models.TextField(
        verbose_name="Описание действия"
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Время действия"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP адрес"
    )
    additional_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Дополнительные данные"
    )

    class Meta:
        verbose_name = "Лог действий пользователя"
        verbose_name_plural = "Логи действий пользователей"
        ordering = ['-timestamp']

    def __str__(self):
        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_time = self.timestamp.astimezone(moscow_tz)
        return f"{self.user.username} - {self.action_type} - {moscow_time.strftime('%d.%m.%Y %H:%M:%S')}"

    def get_moscow_time(self):
        """Возвращает время в московском часовом поясе"""
        moscow_tz = pytz.timezone('Europe/Moscow')
        return self.timestamp.astimezone(moscow_tz)