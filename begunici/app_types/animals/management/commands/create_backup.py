import os
import subprocess
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Create database backup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Create automatic backup (auto_backup_YYYY-MM-DD.sql)',
        )

    def handle(self, *args, **options):
        try:
            # Создаем папку backups если её нет
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)

            # Получаем настройки базы данных
            db_settings = settings.DATABASES['default']
            db_name = db_settings['NAME']
            db_user = db_settings['USER']
            db_password = db_settings['PASSWORD']
            db_host = db_settings['HOST']
            db_port = db_settings['PORT']

            # Формируем имя файла
            now = datetime.now()
            if options['auto']:
                filename = f"auto_backup_{now.strftime('%Y-%m-%d')}.sql"
            else:
                filename = f"backup_{now.strftime('%Y-%m-%d_%H-%M-%S')}.sql"
            
            backup_path = os.path.join(backup_dir, filename)

            # Команда pg_dump
            cmd = [
                'pg_dump',
                f'--host={db_host}',
                f'--port={db_port}',
                f'--username={db_user}',
                '--no-password',
                '--verbose',
                '--clean',
                '--no-owner',
                '--no-privileges',
                db_name
            ]

            # Устанавливаем переменную окружения для пароля
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password

            # Выполняем команду
            with open(backup_path, 'w', encoding='utf-8') as backup_file:
                result = subprocess.run(
                    cmd,
                    stdout=backup_file,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True
                )

            if result.returncode == 0:
                # Если это автобэкап, удаляем старые автобэкапы (оставляем только 3)
                if options['auto']:
                    self.cleanup_auto_backups(backup_dir)
                
                self.stdout.write(
                    self.style.SUCCESS(f'Backup created successfully: {backup_path}')
                )
                return backup_path
            else:
                error_msg = result.stderr
                self.stdout.write(
                    self.style.ERROR(f'Backup failed: {error_msg}')
                )
                # Удаляем неудачный файл
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                raise Exception(f'pg_dump failed: {error_msg}')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating backup: {str(e)}')
            )
            raise e

    def cleanup_auto_backups(self, backup_dir):
        """Удаляет старые автобэкапы, оставляя только 3 последних"""
        try:
            # Получаем все автобэкапы
            auto_backups = []
            for filename in os.listdir(backup_dir):
                if filename.startswith('auto_backup_') and filename.endswith('.sql'):
                    filepath = os.path.join(backup_dir, filename)
                    auto_backups.append((filepath, os.path.getctime(filepath)))
            
            # Сортируем по дате создания (новые первые)
            auto_backups.sort(key=lambda x: x[1], reverse=True)
            
            # Удаляем старые (оставляем только 3)
            for filepath, _ in auto_backups[3:]:
                os.remove(filepath)
                self.stdout.write(f'Removed old auto backup: {filepath}')
                
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Error cleaning up old backups: {str(e)}')
            )