from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
import getpass


class Command(BaseCommand):
    help = 'Создает пользователей с ролями и группы прав'

    def handle(self, *args, **options):
        # Список системных пользователей
        system_users = ['vet', 'zootech', 'main', 'admin']
        
        # Проверяем, есть ли сторонние пользователи
        other_users = User.objects.exclude(username__in=system_users)
        other_users_count = other_users.count()
        
        if other_users_count > 0:
            # Показываем список нестандартных пользователей
            other_usernames = [user.username for user in other_users]
            self.stdout.write(
                self.style.WARNING(f'Найдено {other_users_count} нестандартных пользователей: {", ".join(other_usernames)}')
            )
            
            # Спрашиваем подтверждение
            delete_confirm = input('Удалить всех нестандартных пользователей? (y/n): ').lower().strip()
            
            if delete_confirm == 'y' or delete_confirm == 'yes':
                other_users.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'Удалено {other_users_count} нестандартных пользователей')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('нестандартные пользователи оставлены без изменений')
                )

        # Создаем группы
        vet_group, created = Group.objects.get_or_create(name='Vet')
        zootech_group, created = Group.objects.get_or_create(name='Zootech')
        main_group, created = Group.objects.get_or_create(name='Main')
        admin_group, created = Group.objects.get_or_create(name='Admin')

        # Создаем пользователей (все с маленькой буквы)
        users_data = [
            {'username': 'vet', 'group': vet_group},
            {'username': 'zootech', 'group': zootech_group},
            {'username': 'main', 'group': main_group},
            {'username': 'admin', 'group': admin_group},
        ]

        created_users = []
        updated_users = []

        for user_data in users_data:
            # Запрашиваем пароль для каждого пользователя
            password = getpass.getpass(f'Введите пароль для пользователя {user_data["username"]}: ')
            
            if not password:
                self.stdout.write(self.style.WARNING(f'Пароль для {user_data["username"]} не может быть пустым, пропускаем...'))
                continue

            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'is_active': True,
                }
            )
            
            # Устанавливаем пароль
            user.set_password(password)
            user.save()
            
            if created:
                created_users.append(user.username)
            else:
                updated_users.append(user.username)
            
            # Добавляем в группу
            user.groups.clear()
            user.groups.add(user_data['group'])

        # Настраиваем права для admin группы
        if admin_group:
            admin_group.user_set.update(is_staff=True, is_superuser=True)

        # Выводим результат
        if created_users:
            self.stdout.write(
                self.style.SUCCESS(f'Созданы пользователи: {", ".join(created_users)}')
            )
        
        if updated_users:
            self.stdout.write(
                self.style.SUCCESS(f'Обновлены пароли для: {", ".join(updated_users)}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Операция завершена успешно')
        )