import random
from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Очищает все данные из базы данных с тестом на трезвость'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Пропустить тест на трезвость (используйте осторожно!)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING('ВНИМАНИЕ: Эта команда полностью очистит базу данных!')
        )
        self.stdout.write(
            self.style.WARNING('Все животные, логи и другие данные будут удалены!')
        )
        self.stdout.write(
            self.style.WARNING('Пользователи и их пароли сохранятся.')
        )
        
        # Тест на трезвость (если не используется --force)
        if not options['force']:
            if not self.sobriety_test():
                self.stdout.write(
                    self.style.ERROR('Тест на трезвость не пройден. Операция отменена.')
                )
                return
        
        # Дополнительное подтверждение
        confirm = input('\nВы действительно хотите удалить ВСЕ данные? Введите "УДАЛИТЬ ВСЕ" для подтверждения: ')
        if confirm != 'УДАЛИТЬ ВСЕ':
            self.stdout.write(
                self.style.ERROR('Операция отменена.')
            )
            return
        
        try:
            self.clear_database()
            self.stdout.write(
                self.style.SUCCESS('База данных успешно очищена!')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при очистке базы данных: {e}')
            )

    def sobriety_test(self):
        """Тест на трезвость - решение математической задачи"""
        # Генерируем два двузначных числа
        num1 = random.randint(10, 99)
        num2 = random.randint(10, 99)
        correct_answer = num1 * num2
        
        self.stdout.write(
            self.style.WARNING(f'\nТест на трезвость: Решите пример')
        )
        self.stdout.write(f'   {num1} × {num2} = ?')
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                user_answer = input(f'Введите ответ (попытка {attempt + 1} из {max_attempts}): ')
                user_answer = int(user_answer)
                
                if user_answer == correct_answer:
                    self.stdout.write(
                        self.style.SUCCESS('Правильно! Тест пройден.')
                    )
                    return True
                else:
                    remaining = max_attempts - attempt - 1
                    if remaining > 0:
                        self.stdout.write(
                            self.style.ERROR(f'Неправильно. Осталось попыток: {remaining}')
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'Неправильно. Правильный ответ: {correct_answer}')
                        )
            except ValueError:
                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    self.stdout.write(
                        self.style.ERROR(f'Введите число. Осталось попыток: {remaining}')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Правильный ответ: {correct_answer}')
                    )
        
        return False

    def clear_database(self):
        """Очищает все данные из базы данных, кроме пользователей"""
        self.stdout.write('Начинаю очистку базы данных...')
        
        # Получаем все модели из всех приложений, исключая пользователей
        all_models = []
        excluded_models = ['auth.User', 'auth.Group', 'auth.Permission', 'contenttypes.ContentType']
        
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                model_label = model._meta.label
                if model_label not in excluded_models:
                    all_models.append(model)
        
        # Сортируем модели по зависимостям (сначала удаляем зависимые)
        models_to_clear = []
        
        # Сначала добавляем модели без внешних ключей
        for model in all_models:
            if not any(field.related_model for field in model._meta.get_fields() 
                      if hasattr(field, 'related_model') and field.related_model):
                models_to_clear.append(model)
        
        # Затем добавляем остальные модели
        for model in all_models:
            if model not in models_to_clear:
                models_to_clear.append(model)
        
        # Отключаем проверку внешних ключей для PostgreSQL
        with connection.cursor() as cursor:
            cursor.execute('SET session_replication_role = replica;')
        
        try:
            # Удаляем данные из всех таблиц
            deleted_counts = {}
            for model in reversed(models_to_clear):  # Обратный порядок для безопасности
                try:
                    count = model.objects.count()
                    if count > 0:
                        model.objects.all().delete()
                        deleted_counts[model._meta.label] = count
                        self.stdout.write(f'   {model._meta.label}: удалено {count} записей')
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'   Не удалось очистить {model._meta.label}: {e}')
                    )
            
            # Сбрасываем последовательности для PostgreSQL (кроме пользователей)
            with connection.cursor() as cursor:
                # Получаем все последовательности
                cursor.execute("""
                    SELECT sequence_name FROM information_schema.sequences 
                    WHERE sequence_schema = 'public'
                    AND sequence_name NOT LIKE 'auth_%';
                """)
                sequences = cursor.fetchall()
                
                # Сбрасываем каждую последовательность
                for (sequence_name,) in sequences:
                    cursor.execute(f'ALTER SEQUENCE {sequence_name} RESTART WITH 1;')
            
            # Показываем итоги
            total_deleted = sum(deleted_counts.values())
            self.stdout.write(f'\nИтого удалено записей: {total_deleted}')
            
            if deleted_counts:
                self.stdout.write('\nДетализация по моделям:')
                for model_label, count in sorted(deleted_counts.items()):
                    self.stdout.write(f'   • {model_label}: {count}')
            
            # Показываем сохраненных пользователей
            user_count = User.objects.count()
            if user_count > 0:
                self.stdout.write(f'\nСохранено пользователей: {user_count}')
                users = User.objects.all().values_list('username', flat=True)
                self.stdout.write('Пользователи: ' + ', '.join(users))
        
        finally:
            # Включаем обратно проверку внешних ключей для PostgreSQL
            with connection.cursor() as cursor:
                cursor.execute('SET session_replication_role = DEFAULT;')