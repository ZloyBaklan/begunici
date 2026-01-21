from django.conf import settings
from django.db import models
from django.utils import timezone


class Note(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
        verbose_name="Пользователь",
    )
    date = models.DateField(
        default=timezone.localdate,
        db_index=True,
        verbose_name="Дата заметки",
    )
    text = models.TextField(verbose_name="Текст заметки")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self):
        return f"{self.user} {self.date}: {self.text[:40]}"
