import getpass
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Создаёт или обновляет сервисного пользователя scales"

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            help="Пароль пользователя scales; безопаснее передать через SCALES_SERVICE_PASSWORD",
        )

    def handle(self, *args, **options):
        password = (
            options.get("password")
            or os.getenv("SCALES_SERVICE_PASSWORD")
            or getpass.getpass("Введите пароль для пользователя scales: ")
        )
        if not password:
            raise CommandError("Пароль пользователя scales не может быть пустым")

        user, created = User.objects.get_or_create(username="scales")
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(password)
        user.save()
        user.groups.clear()
        user.user_permissions.clear()

        action = "создан" if created else "обновлён"
        self.stdout.write(
            self.style.SUCCESS(f"Сервисный пользователь scales {action}")
        )
