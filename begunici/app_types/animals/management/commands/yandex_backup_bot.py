import os
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand
from decouple import config
import yadisk


class Command(BaseCommand):
    help = 'Диск bot для загрузки новых бэкапов на облачное хранилище'

    def __init__(self):
        super().__init__()
        self.client_id = config('YANDEX_CLIENT_ID')
        self.client_secret = config('YANDEX_CLIENT_SECRET')
        self.access_token = config('YANDEX_ACCESS_TOKEN')
        self.folder_path = config('YANDEX_FOLDER_PATH', default='/backups')
        
        self.backups_dir = Path("backups")
        self.uploaded_files_path = self.backups_dir / "uploaded_files.json"
        self.log_file_path = self.backups_dir / "yandex_bot_errors.log"
        
        self.yadisk = yadisk.YaDisk(token=self.access_token)
        
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file_path, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-once',
            action='store_true',
            help='Проверить папку один раз и выйти (для тестирования)',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Показать статус бота и управление',
        )
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Запуск в режиме демона (фоновый режим)',
        )

    def handle(self, *args, **options):
        if options['daemon']:
            # Создаем файл для отслеживания загруженных файлов, если его нет
            if not self.uploaded_files_path.exists():
                self.save_uploaded_files({})
            self.run_daemon_mode()
        elif options['status']:
            self.show_status_and_manage()
        elif options['check_once']:
            self.logger.info("Запуск бота для мониторинга бэкапов")
            # Создаем файл для отслеживания загруженных файлов, если его нет
            if not self.uploaded_files_path.exists():
                self.save_uploaded_files({})
            self.check_for_new_backups()
        else:
            self.show_status_and_manage()

    def run_continuous_monitoring(self):
        """Непрерывный мониторинг папки с бэкапами"""
        self.logger.info("Начат непрерывный мониторинг папки backups")
        
        while True:
            try:
                self.check_for_new_backups()
                time.sleep(60)  # Проверяем каждую минуту
            except KeyboardInterrupt:
                self.logger.info("Остановка бота по запросу пользователя")
                break
            except Exception as e:
                self.logger.error(f"Ошибка в основном цикле: {e}")
                time.sleep(60)  # Ждем минуту перед повторной попыткой

    def check_for_new_backups(self):
        """Проверка папки на новые бэкапы"""
        try:
            if not self.backups_dir.exists():
                self.logger.warning(f"Папка {self.backups_dir} не существует")
                return

            uploaded_files = self.load_uploaded_files()
            sql_files = list(self.backups_dir.glob("*.sql"))
            
            for file_path in sql_files:
                file_key = f"{file_path.name}_{file_path.stat().st_mtime}"
                
                if file_key not in uploaded_files:
                    self.logger.info(f"Найден новый бэкап: {file_path.name}")
                    if self.upload_backup_to_yandex(file_path):
                        uploaded_files[file_key] = {
                            'filename': file_path.name,
                            'uploaded_at': datetime.now().isoformat(),
                            'file_size': file_path.stat().st_size
                        }
                        self.save_uploaded_files(uploaded_files)
                        self.logger.info(f"Бэкап {file_path.name} успешно загружен на Диск")
                    else:
                        self.logger.error(f"Не удалось загрузить бэкап {file_path.name}")

        except Exception as e:
            self.logger.error(f"Ошибка при проверке новых бэкапов: {e}")

    def upload_backup_to_yandex(self, file_path):
        try:
            # Создаем папку backups, если её нет
            if not self.yadisk.exists(self.folder_path):
                self.yadisk.mkdir(self.folder_path)
                self.logger.info(f"Создана папка {self.folder_path} на Диск")
            
            # Определяем путь к файлу на диске
            remote_path = f"{self.folder_path}/{file_path.name}"
            
            # Получаем информацию о файле
            file_stat = file_path.stat()
            file_size = self.format_file_size(file_stat.st_size)
            file_date = datetime.fromtimestamp(file_stat.st_mtime).strftime("%d.%m.%Y %H:%M")
            backup_type = self.determine_backup_type(file_path.name)
            
            self.logger.info(f"Загрузка файла {file_path.name} ({file_size}) на Диск...")
            
            # Загружаем файл (с перезаписью, если существует)
            self.yadisk.upload(str(file_path), remote_path, overwrite=True)
            
            self.logger.info(f"Файл успешно загружен: {remote_path}")
            self.logger.info(f"Тип: {backup_type}, Дата: {file_date}, Размер: {file_size}")
            
            return True
                    
        except yadisk.exceptions.YaDiskError as e:
            self.logger.error(f"Ошибка Я.ДИСК API при загрузке {file_path.name}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке файла {file_path.name}: {e}")
            return False

    def determine_backup_type(self, filename):
        """Определение типа бэкапа по имени файла"""
        filename_lower = filename.lower()
        
        if 'auto' in filename_lower:
            return "Автоматический бэкап"
        elif 'backup_' in filename_lower and '_' in filename_lower:
            return "Ручной бэкап"
        elif 'safety' in filename_lower:
            return "Безопасный бэкап"
        elif 'full' in filename_lower:
            return "Полный бэкап"
        else:
            return "Бэкап"

    def format_file_size(self, size_bytes):
        """Форматирование размера файла"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def load_uploaded_files(self):
        """Загрузка списка загруженных файлов"""
        try:
            if self.uploaded_files_path.exists():
                with open(self.uploaded_files_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке списка загруженных файлов: {e}")
            return {}

    def save_uploaded_files(self, uploaded_files):
        """Сохранение списка загруженных файлов"""
        try:
            with open(self.uploaded_files_path, 'w', encoding='utf-8') as f:
                json.dump(uploaded_files, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении списка загруженных файлов: {e}")

    def show_status_and_manage(self):
        """Показать статус бота и интерактивное управление"""
        self.print_header()
        
        # Создаем файл для отслеживания загруженных файлов, если его нет
        if not self.uploaded_files_path.exists():
            self.save_uploaded_files({})
        
        while True:
            self.print_status()
            choice = self.get_user_choice()
            
            if choice == '1':
                self.start_background_monitoring()
                input("\nНажмите Enter для продолжения...")
            elif choice == '2':
                self.stop_background_monitoring()
                input("\nНажмите Enter для продолжения...")
            elif choice == '3':
                self.check_for_new_backups()
                input("\nНажмите Enter для продолжения...")
            elif choice == '4':
                self.show_error_logs()
                input("\nНажмите Enter для продолжения...")
            elif choice == '5':
                self.clear_uploaded_files()
                input("\nНажмите Enter для продолжения...")
            elif choice == '6':
                self.show_disk_info()
                input("\nНажмите Enter для продолжения...")
            elif choice == '7':
                self.list_remote_files()
                input("\nНажмите Enter для продолжения...")
            elif choice == '0':
                break
            else:
                print("\nНеверный выбор. Попробуйте снова.")
                input("Нажмите Enter для продолжения...")

    def print_header(self):
        """Печать заголовка"""
        print("=" * 60)
        print("Я.Диск BOT - УПРАВЛЕНИЕ БЭКАПАМИ")
        print("=" * 60)

    def print_status(self):
        """Печать текущего статуса бота"""
        print("\nТЕКУЩИЙ СТАТУС БОТА:")
        print("-" * 40)
        
        # Проверяем папку backups
        if self.backups_dir.exists():
            sql_files = list(self.backups_dir.glob("*.sql"))
            print(f"Папка бэкапов: Найдено {len(sql_files)} .sql файлов")
        else:
            print("Папка бэкапов: Не найдена")
        
        # Проверяем загруженные файлы
        uploaded_files = self.load_uploaded_files()
        print(f"Загружено файлов: {len(uploaded_files)}")
        
        # Проверяем последнюю активность
        if uploaded_files:
            last_uploaded = max(uploaded_files.values(), key=lambda x: x['uploaded_at'])
            print(f"Последняя загрузка: {last_uploaded['filename']} ({last_uploaded['uploaded_at'][:19]})")
        else:
            print("Последняя загрузка: Нет данных")
        
        yandex_status = self.test_yandex_connection()
        if yandex_status:
            print("Я.Диск: Подключение работает")
        else:
            print("Я.Диск: Проблемы с подключением")
        
        # Проверяем статус фонового процесса
        bg_status = self.check_background_status()
        print(f"Фоновый мониторинг: {bg_status}")
        
        print("-" * 40)

    def get_user_choice(self):
        """Получить выбор пользователя"""
        print("\nУПРАВЛЕНИЕ БОТОМ:")
        print("1. Запустить мониторинг в фоне")
        print("2. Остановить фоновый мониторинг")
        print("3. Проверить новые бэкапы (один раз)")
        print("4. Показать логи ошибок")
        print("5. Очистить список загруженных файлов")
        print("6. Информация о Диске")
        print("7. Список файлов на диске")
        print("0. Выход")
        print("-" * 40)
        
        return input("Выберите действие (0-7): ").strip()

    def test_yandex_connection(self):
        """Тестирование подключения к я диску"""
        try:
            return self.yadisk.check_token()
        except:
            return False

    def show_disk_info(self):
        """Показать информацию о диске"""
        print("\nИНФОРМАЦИЯ О Я.Диск:")
        print("-" * 40)
        
        try:
            if self.yadisk.check_token():
                disk_info = self.yadisk.get_disk_info()
                
                total_space = self.format_file_size(disk_info.total_space)
                used_space = self.format_file_size(disk_info.used_space)
                free_space = self.format_file_size(disk_info.total_space - disk_info.used_space)
                
                print(f"Общий объем: {total_space}")
                print(f"Использовано: {used_space}")
                print(f"Свободно: {free_space}")
                print(f"Папка бэкапов: {self.folder_path}")
                
                # Проверяем существование папки бэкапов
                if self.yadisk.exists(self.folder_path):
                    print("Папка бэкапов: Существует")
                else:
                    print("Папка бэкапов: Не создана")
            else:
                print("Ошибка: Неверный токен доступа")
        except Exception as e:
            print(f"Ошибка получения информации: {e}")

    def list_remote_files(self):
        """Показать список файлов в папке бэкапов на диске"""
        print(f"\nФАЙЛЫ В ПАПКЕ {self.folder_path}:")
        print("-" * 40)
        
        try:
            if not self.yadisk.exists(self.folder_path):
                print("Папка бэкапов не существует на диске")
                return
            
            files = list(self.yadisk.listdir(self.folder_path))
            
            if not files:
                print("Папка пуста")
                return
            
            # Сортируем по дате изменения (новые сверху)
            files.sort(key=lambda x: x.modified, reverse=True)
            
            print(f"Найдено файлов: {len(files)}")
            print()
            
            for file_info in files[:20]:  # Показываем последние 20 файлов
                if file_info.type == 'file' and file_info.name.endswith('.sql'):
                    size = self.format_file_size(file_info.size)
                    date = file_info.modified.strftime("%d.%m.%Y %H:%M")
                    backup_type = self.determine_backup_type(file_info.name)
                    print(f"{file_info.name}")
                    print(f"  Размер: {size} | Дата: {date} | Тип: {backup_type}")
                    print()
            
            if len(files) > 20:
                print(f"... и еще {len(files) - 20} файлов")
                
        except Exception as e:
            print(f"Ошибка получения списка файлов: {e}")

    def show_error_logs(self):
        """Показать логи ошибок"""
        print("\nЛОГИ ОШИБОК:")
        print("-" * 40)
        
        try:
            if self.log_file_path.exists():
                with open(self.log_file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                    # Фильтруем только строки с ошибками
                    error_lines = [line for line in lines if 'ERROR' in line or 'ОШИБКА' in line.upper()]
                    
                    if error_lines:
                        # Показываем последние 15 строк с ошибками
                        recent_errors = error_lines[-15:] if len(error_lines) > 15 else error_lines
                        
                        for line in recent_errors:
                            print(line.strip())
                        
                        print(f"\nВсего ошибок в логе: {len(error_lines)}")
                    else:
                        print("Ошибок не найдено")
            else:
                print("Лог файл не найден")
        except Exception as e:
            print(f"Ошибка чтения логов: {e}")

    def clear_uploaded_files(self):
        """Очистить список загруженных файлов"""
        print("\nОЧИСТКА СПИСКА ЗАГРУЖЕННЫХ ФАЙЛОВ")
        print("-" * 40)
        
        uploaded_files = self.load_uploaded_files()
        if not uploaded_files:
            print("Список уже пуст")
            return
        
        print(f"Будет удалена информация о {len(uploaded_files)} загруженных файлах")
        print("ВНИМАНИЕ: После очистки все файлы будут загружены заново!")
        
        confirm = input("\nВы уверены? (да/нет): ").strip().lower()
        
        if confirm in ['да', 'yes', 'y', 'д']:
            self.save_uploaded_files({})
            print("Список загруженных файлов очищен")
            self.logger.info("Список загруженных файлов очищен пользователем")
        else:
            print("Операция отменена")

    def check_background_status(self):
        """Проверить статус фонового процесса"""
        pid_file = self.backups_dir / "yandex_bot.pid"
        
        if not pid_file.exists():
            return "Не запущен"
        
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Проверяем, существует ли процесс
            import os
            import signal
            try:
                os.kill(pid, 0)  # Не убивает процесс, только проверяет существование
                return f"Запущен (PID: {pid})"
            except OSError:
                # Процесс не существует, удаляем старый PID файл
                pid_file.unlink()
                return "Не запущен"
        except:
            return "Неизвестно"

    def start_background_monitoring(self):
        """Запуск мониторинга в фоновом режиме"""
        print("\nЗАПУСК ФОНОВОГО МОНИТОРИНГА")
        print("-" * 40)
        
        # Проверяем, не запущен ли уже
        if self.check_background_status() != "Не запущен":
            print("Фоновый мониторинг уже запущен")
            return
        
        try:
            import subprocess
            import os
            
            # Команда для запуска в фоне внутри контейнера
            cmd = [
                "nohup", "python", "manage.py", "yandex_backup_bot", "--daemon"
            ]
            
            # Запускаем процесс в фоне
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Даем процессу время запуститься
            import time
            time.sleep(2)
            
            # Проверяем статус
            status = self.check_background_status()
            if "Запущен" in status:
                print("Фоновый мониторинг запущен успешно")
                print("Бот будет работать в фоне и проверять папку каждую минуту")
                print("Логи записываются в backups/yandex_bot_errors.log")
                print(f"Статус: {status}")
            else:
                print("Не удалось запустить фоновый процесс")
                
        except Exception as e:
            print(f"Ошибка при запуске фонового процесса: {e}")
            print("\nАльтернативный способ:")
            print("Запустите в отдельном терминале:")
            print("docker-compose exec web python manage.py yandex_backup_bot --daemon")

    def stop_background_monitoring(self):
        """Остановка фонового мониторинга"""
        print("\nОСТАНОВКА ФОНОВОГО МОНИТОРИНГА")
        print("-" * 40)
        
        pid_file = self.backups_dir / "yandex_bot.pid"
        
        if not pid_file.exists():
            print("Фоновый мониторинг не запущен")
            return
        
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            import os
            import signal
            
            # Пытаемся остановить процесс
            try:
                os.kill(pid, signal.SIGTERM)
                pid_file.unlink()
                print(f"Фоновый процесс (PID: {pid}) остановлен")
                self.logger.info(f"Фоновый процесс остановлен пользователем (PID: {pid})")
            except OSError:
                # Процесс уже не существует
                pid_file.unlink()
                print("Процесс уже был остановлен")
                
        except Exception as e:
            print(f"Ошибка при остановке процесса: {e}")

    def run_daemon_mode(self):
        """Запуск в режиме демона"""
        import os
        
        # Записываем PID в файл
        pid_file = self.backups_dir / "yandex_bot.pid"
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        self.logger.info("Запуск бота в режиме демона")
        
        try:
            self.run_continuous_monitoring()
        finally:
            # Удаляем PID файл при завершении
            if pid_file.exists():
                pid_file.unlink()