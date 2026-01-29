import os
import glob
from datetime import datetime, timedelta
from django.conf import settings
from django.core.management import call_command
from io import StringIO


class BackupManager:
    def __init__(self):
        self.backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_manual_backup(self):
        """Создает ручной бэкап"""
        try:
            # Перехватываем вывод команды
            out = StringIO()
            call_command('create_backup', stdout=out)
            
            # Получаем путь к созданному файлу из вывода
            output = out.getvalue()
            if 'Backup created successfully:' in output:
                return True, "Бэкап успешно создан"
            else:
                return False, "Ошибка при создании бэкапа"
                
        except Exception as e:
            return False, f"Ошибка: {str(e)}"

    def create_auto_backup(self):
        """Создает автоматический бэкап"""
        try:
            out = StringIO()
            call_command('create_backup', '--auto', stdout=out)
            
            output = out.getvalue()
            if 'Backup created successfully:' in output:
                return True, "Автобэкап успешно создан"
            else:
                return False, "Ошибка при создании автобэкапа"
                
        except Exception as e:
            return False, f"Ошибка: {str(e)}"

    def get_last_backup_info(self):
        """Возвращает информацию о последнем бэкапе"""
        try:
            # Ищем все файлы бэкапов
            backup_files = glob.glob(os.path.join(self.backup_dir, '*.sql'))
            
            if not backup_files:
                return None
            
            # Находим самый новый файл
            latest_file = max(backup_files, key=os.path.getctime)
            filename = os.path.basename(latest_file)
            
            # Определяем тип бэкапа
            if filename.startswith('auto_backup_'):
                backup_type = 'Автоматический'
            else:
                backup_type = 'Ручной'
            
            # Получаем дату создания
            creation_time = datetime.fromtimestamp(os.path.getctime(latest_file))
            
            return {
                'filename': filename,
                'type': backup_type,
                'date': creation_time.strftime('%d.%m.%Y %H:%M'),
                'size': self._format_file_size(os.path.getsize(latest_file))
            }
            
        except Exception as e:
            return None

    def should_create_auto_backup(self):
        """Проверяет, нужно ли создавать автобэкап"""
        try:
            # Ищем последний автобэкап
            auto_backups = glob.glob(os.path.join(self.backup_dir, 'auto_backup_*.sql'))
            
            if not auto_backups:
                return True  # Нет автобэкапов, нужно создать
            
            # Находим самый новый автобэкап
            latest_auto = max(auto_backups, key=os.path.getctime)
            last_backup_time = datetime.fromtimestamp(os.path.getctime(latest_auto))
            
            # Проверяем, прошло ли 3 дня
            return datetime.now() - last_backup_time >= timedelta(days=3)
            
        except Exception as e:
            return True  # В случае ошибки лучше создать бэкап

    def _format_file_size(self, size_bytes):
        """Форматирует размер файла в читаемый вид"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"


# Глобальный экземпляр менеджера бэкапов
backup_manager = BackupManager()