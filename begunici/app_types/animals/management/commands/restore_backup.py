import os
import subprocess
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Restore database from backup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Specific backup file to restore (skip interactive selection)',
        )
        parser.add_argument(
            '--number',
            type=int,
            help='Backup number from list (use --list to see numbers)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompts (dangerous!)',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List available backups and exit',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("=" * 60))
        self.stdout.write(self.style.WARNING("ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ ИЗ БЭКАПА"))
        self.stdout.write(self.style.WARNING("=" * 60))
        self.stdout.write(self.style.ERROR("ВНИМАНИЕ: Эта операция ПОЛНОСТЬЮ ЗАМЕНИТ текущую базу данных!"))
        self.stdout.write(self.style.ERROR("Все текущие данные будут БЕЗВОЗВРАТНО УТЕРЯНЫ!"))
        self.stdout.write("")

        try:
            # Получаем путь к папке с бэкапами
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            
            if not os.path.exists(backup_dir):
                self.stdout.write(self.style.ERROR("Папка с бэкапами не найдена!"))
                return

            # Если запрошен только список бэкапов
            if options['list']:
                self.list_backups(backup_dir)
                return

            # Выбираем файл бэкапа
            if options['file']:
                backup_file = options['file']
                if not os.path.isabs(backup_file):
                    backup_file = os.path.join(backup_dir, backup_file)
            elif options['number']:
                backup_file = self.get_backup_by_number(backup_dir, options['number'])
            else:
                backup_file = self.select_backup_file(backup_dir)
                
            if not backup_file:
                self.stdout.write("Операция отменена.")
                return

            # Проверяем существование файла
            if not os.path.exists(backup_file):
                self.stdout.write(self.style.ERROR(f"Файл бэкапа не найден: {backup_file}"))
                return

            # Показываем информацию о файле
            self.show_backup_info(backup_file)

            # Тест на трезвость и подтверждение
            if not options['force']:
                if not self.confirm_restore():
                    self.stdout.write("Операция отменена.")
                    return

            # Создаем бэкап текущей БД перед восстановлением
            self.stdout.write("Создаем бэкап текущей БД перед восстановлением...")
            current_backup = self.create_safety_backup()
            
            # Восстанавливаем БД
            self.restore_database(backup_file)
            
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(self.style.SUCCESS("База данных успешно восстановлена!"))
            self.stdout.write(self.style.SUCCESS(f"Бэкап текущей БД сохранен: {current_backup}"))
            self.stdout.write(self.style.SUCCESS("=" * 60))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка восстановления: {str(e)}"))
            raise e

    def list_backups(self, backup_dir):
        """Показывает список доступных бэкапов"""
        backup_files = []
        for filename in os.listdir(backup_dir):
            if filename.endswith('.sql'):
                filepath = os.path.join(backup_dir, filename)
                file_size = os.path.getsize(filepath)
                file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                backup_files.append((filename, filepath, file_size, file_time))

        if not backup_files:
            self.stdout.write(self.style.ERROR("Файлы бэкапов не найдены!"))
            return

        # Сортируем по дате (новые первые)
        backup_files.sort(key=lambda x: x[3], reverse=True)

        self.stdout.write("Доступные бэкапы:")
        self.stdout.write("-" * 80)
        for i, (filename, filepath, file_size, file_time) in enumerate(backup_files, 1):
            size_mb = file_size / (1024 * 1024)
            time_str = file_time.strftime("%Y-%m-%d %H:%M:%S")
            backup_type = "Auto" if filename.startswith('auto_backup_') else "Manual"
            self.stdout.write(f"{i:2d}. {backup_type} | {filename} | {size_mb:.1f} MB | {time_str}")
        self.stdout.write("-" * 80)
        self.stdout.write("")
        self.stdout.write("Для восстановления используйте:")
        self.stdout.write("python manage.py restore_backup --number <номер> --force")
        self.stdout.write("Например: python manage.py restore_backup --number 1 --force")

    def get_backup_by_number(self, backup_dir, number):
        """Получает файл бэкапа по номеру из списка"""
        backup_files = []
        for filename in os.listdir(backup_dir):
            if filename.endswith('.sql'):
                filepath = os.path.join(backup_dir, filename)
                file_size = os.path.getsize(filepath)
                file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                backup_files.append((filename, filepath, file_size, file_time))

        if not backup_files:
            self.stdout.write(self.style.ERROR("Файлы бэкапов не найдены!"))
            return None

        # Сортируем по дате (новые первые)
        backup_files.sort(key=lambda x: x[3], reverse=True)

        if number < 1 or number > len(backup_files):
            self.stdout.write(self.style.ERROR(f"Неверный номер бэкапа: {number}"))
            self.stdout.write(f"Доступные номера: 1-{len(backup_files)}")
            return None

        selected_backup = backup_files[number - 1]
        self.stdout.write(f"Выбран бэкап #{number}: {selected_backup[0]}")
        return selected_backup[1]

    def select_backup_file(self, backup_dir):
        """Интерактивный выбор файла бэкапа"""
        # Получаем список файлов бэкапов
        backup_files = []
        for filename in os.listdir(backup_dir):
            if filename.endswith('.sql'):
                filepath = os.path.join(backup_dir, filename)
                file_size = os.path.getsize(filepath)
                file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                backup_files.append((filename, filepath, file_size, file_time))

        if not backup_files:
            self.stdout.write(self.style.ERROR("Файлы бэкапов не найдены!"))
            return None

        # Сортируем по дате (новые первые)
        backup_files.sort(key=lambda x: x[3], reverse=True)

        # Показываем список
        self.stdout.write("Доступные бэкапы:")
        self.stdout.write("-" * 80)
        for i, (filename, filepath, file_size, file_time) in enumerate(backup_files, 1):
            size_mb = file_size / (1024 * 1024)
            time_str = file_time.strftime("%Y-%m-%d %H:%M:%S")
            backup_type = "Auto" if filename.startswith('auto_backup_') else "Manual"
            self.stdout.write(f"{i:2d}. {backup_type} | {filename} | {size_mb:.1f} MB | {time_str}")

        self.stdout.write("-" * 80)

        # Запрашиваем выбор
        while True:
            try:
                choice = input("Введите номер бэкапа для восстановления (0 - отмена): ")
                
                if choice == '0':
                    return None
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(backup_files):
                    selected_file = backup_files[choice_num - 1][1]
                    self.stdout.write(f"Выбран: {backup_files[choice_num - 1][0]}")
                    return selected_file
                else:
                    self.stdout.write(self.style.ERROR("Неверный номер. Попробуйте еще раз."))
                    
            except ValueError:
                self.stdout.write(self.style.ERROR("Введите число. Попробуйте еще раз."))
            except KeyboardInterrupt:
                self.stdout.write("\nОперация отменена.")
                return None

    def show_backup_info(self, backup_file):
        """Показывает информацию о выбранном бэкапе"""
        filename = os.path.basename(backup_file)
        file_size = os.path.getsize(backup_file)
        file_time = datetime.fromtimestamp(os.path.getctime(backup_file))
        
        self.stdout.write("")
        self.stdout.write("ИНФОРМАЦИЯ О БЭКАПЕ:")
        self.stdout.write("-" * 40)
        self.stdout.write(f"Файл: {filename}")
        self.stdout.write(f"Размер: {file_size / (1024 * 1024):.1f} MB")
        self.stdout.write(f"Создан: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write("")

    def confirm_restore(self):
        """Тест на трезвость и подтверждение"""
        self.stdout.write(self.style.ERROR("ТЕСТ НА ТРЕЗВОСТЬ:"))
        self.stdout.write("Для подтверждения введите: ВОССТАНОВИТЬ")
        
        try:
            confirmation = input("Введите слово: ")
            
            if confirmation != "ВОССТАНОВИТЬ":
                self.stdout.write(self.style.ERROR("Неверное слово подтверждения!"))
                return False
            
            # Дополнительное подтверждение
            final_confirm = input("Вы уверены? Все данные будут заменены! (да/нет): ")
            
            return final_confirm.lower() in ['да', 'yes', 'y']
            
        except KeyboardInterrupt:
            self.stdout.write("\nОперация отменена.")
            return False

    def create_safety_backup(self):
        """Создает страховочный бэкап текущей БД"""
        from django.core.management import call_command
        
        # Создаем бэкап с префиксом safety_
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        now = datetime.now()
        safety_filename = f"safety_backup_{now.strftime('%Y-%m-%d_%H-%M-%S')}.sql"
        safety_path = os.path.join(backup_dir, safety_filename)
        
        # Получаем настройки БД
        db_settings = settings.DATABASES['default']
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_password = db_settings['PASSWORD']
        db_host = db_settings['HOST']
        db_port = db_settings['PORT']

        # Команда pg_dump
        cmd = [
            'pg_dump',
            f'--host={db_host}',
            f'--port={db_port}',
            f'--username={db_user}',
            '--no-password',
            '--clean',
            '--no-owner',
            '--no-privileges',
            db_name
        ]

        env = os.environ.copy()
        env['PGPASSWORD'] = db_password

        with open(safety_path, 'w', encoding='utf-8') as backup_file:
            result = subprocess.run(
                cmd,
                stdout=backup_file,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )

        if result.returncode != 0:
            raise Exception(f"Не удалось создать страховочный бэкап: {result.stderr}")
        
        return safety_path

    def restore_database(self, backup_file):
        """Восстанавливает базу данных из файла"""
        self.stdout.write("Восстанавливаем базу данных...")
        
        # Получаем настройки БД
        db_settings = settings.DATABASES['default']
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_password = db_settings['PASSWORD']
        db_host = db_settings['HOST']
        db_port = db_settings['PORT']

        # Команда psql для восстановления
        cmd = [
            'psql',
            f'--host={db_host}',
            f'--port={db_port}',
            f'--username={db_user}',
            '--no-password',
            '--dbname=' + db_name,
            '--file=' + backup_file
        ]

        env = os.environ.copy()
        env['PGPASSWORD'] = db_password

        # Выполняем восстановление
        result = subprocess.run(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=env,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Ошибка восстановления БД: {result.stderr}")
        
        self.stdout.write("База данных восстановлена из бэкапа.")