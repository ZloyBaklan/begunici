from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from begunici.app_types.veterinary.vet_models import Veterinary, VeterinaryCare
from datetime import datetime


class Command(BaseCommand):
    help = 'Обновляет сроки действия существующих ветобработок в соответствии с текущими настройками в справочнике'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать изменения без их применения',
        )
        parser.add_argument(
            '--care-type',
            type=str,
            help='Обновить только записи с указанным типом обработки',
        )
        parser.add_argument(
            '--care-name',
            type=str,
            help='Обновить только записи с указанным названием обработки',
        )
        parser.add_argument(
            '--after-date',
            type=str,
            help='Обновить только записи после указанной даты (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--before-date',
            type=str,
            help='Обновить только записи до указанной даты (YYYY-MM-DD)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        care_type = options.get('care_type')
        care_name = options.get('care_name')
        after_date = options.get('after_date')
        before_date = options.get('before_date')

        # Валидация дат
        after_date_obj = None
        before_date_obj = None
        
        if after_date:
            try:
                after_date_obj = datetime.strptime(after_date, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError(f'Неверный формат даты --after-date: {after_date}. Используйте YYYY-MM-DD')
        
        if before_date:
            try:
                before_date_obj = datetime.strptime(before_date, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError(f'Неверный формат даты --before-date: {before_date}. Используйте YYYY-MM-DD')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('=== РЕЖИМ ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА (DRY RUN) ===')
            )
            self.stdout.write('Изменения НЕ будут применены к базе данных\n')

        # Строим запрос для фильтрации ветобработок
        queryset = Veterinary.objects.select_related('veterinary_care', 'tag').all()

        # Применяем фильтры
        if care_type:
            queryset = queryset.filter(veterinary_care__care_type__icontains=care_type)
        
        if care_name:
            queryset = queryset.filter(veterinary_care__care_name__icontains=care_name)
        
        if after_date_obj:
            queryset = queryset.filter(date_of_care__date__gte=after_date_obj)
        
        if before_date_obj:
            queryset = queryset.filter(date_of_care__date__lte=before_date_obj)

        # Получаем все записи для обработки
        vet_records = list(queryset.order_by('date_of_care'))
        
        if not vet_records:
            self.stdout.write(
                self.style.WARNING('Не найдено ветобработок для обновления с указанными фильтрами.')
            )
            return

        self.stdout.write(f'Найдено {len(vet_records)} записей для обработки\n')

        # Показываем применяемые фильтры
        if care_type or care_name or after_date or before_date:
            self.stdout.write('Применяемые фильтры:')
            if care_type:
                self.stdout.write(f'  - Тип обработки содержит: "{care_type}"')
            if care_name:
                self.stdout.write(f'  - Название обработки содержит: "{care_name}"')
            if after_date:
                self.stdout.write(f'  - Дата обработки после: {after_date}')
            if before_date:
                self.stdout.write(f'  - Дата обработки до: {before_date}')
            self.stdout.write('')

        # Группируем изменения по типам обработок
        changes_by_care = {}
        total_changes = 0
        
        for vet_record in vet_records:
            if not vet_record.veterinary_care:
                continue
                
            current_duration = vet_record.duration_days
            new_duration = vet_record.veterinary_care.default_duration_days
            
            # Проверяем, нужно ли обновление
            if current_duration != new_duration:
                care_key = f"{vet_record.veterinary_care.care_type} - {vet_record.veterinary_care.care_name}"
                
                if care_key not in changes_by_care:
                    changes_by_care[care_key] = {
                        'care_obj': vet_record.veterinary_care,
                        'records': []
                    }
                
                changes_by_care[care_key]['records'].append({
                    'vet_record': vet_record,
                    'old_duration': current_duration,
                    'new_duration': new_duration
                })
                total_changes += 1

        if total_changes == 0:
            self.stdout.write(
                self.style.SUCCESS('Все записи уже имеют актуальные сроки действия. Обновление не требуется.')
            )
            return

        # Показываем детали изменений
        self.stdout.write(f'Будет обновлено {total_changes} записей:\n')
        
        for care_key, care_data in changes_by_care.items():
            care_obj = care_data['care_obj']
            records = care_data['records']
            
            self.stdout.write(
                self.style.HTTP_INFO(f'📋 {care_key}')
            )
            self.stdout.write(f'   Новый срок действия: {care_obj.default_duration_days} дней')
            self.stdout.write(f'   Количество записей: {len(records)}')
            
            # Показываем первые несколько записей как примеры
            for i, record_data in enumerate(records[:3]):
                vet_record = record_data['vet_record']
                old_duration = record_data['old_duration']
                new_duration = record_data['new_duration']
                
                care_date = vet_record.date_of_care
                if hasattr(care_date, 'date'):
                    care_date_str = care_date.date().strftime('%d.%m.%Y')
                else:
                    care_date_str = care_date.strftime('%d.%m.%Y')
                
                self.stdout.write(
                    f'   • {vet_record.tag.tag_number} ({care_date_str}): {old_duration} → {new_duration} дней'
                )
            
            if len(records) > 3:
                self.stdout.write(f'   ... и ещё {len(records) - 3} записей')
            
            self.stdout.write('')

        # Применяем изменения (если не dry-run)
        if not dry_run:
            try:
                with transaction.atomic():
                    updated_count = 0
                    
                    for care_key, care_data in changes_by_care.items():
                        for record_data in care_data['records']:
                            vet_record = record_data['vet_record']
                            new_duration = record_data['new_duration']
                            
                            vet_record.duration_days = new_duration
                            vet_record.save(update_fields=['duration_days'])
                            updated_count += 1
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Успешно обновлено {updated_count} записей!')
                    )
                    
            except Exception as e:
                raise CommandError(f'Ошибка при обновлении записей: {str(e)}')
        
        else:
            self.stdout.write(
                self.style.WARNING('=== КОНЕЦ ПРЕДВАРИТЕЛЬНОГО ПРОСМОТРА ===')
            )
            self.stdout.write('Для применения изменений запустите команду без флага --dry-run')

        # Показываем примеры команд для запуска
        self.stdout.write('\n' + '='*60)
        self.stdout.write('Примеры использования команды:')
        self.stdout.write('')
        self.stdout.write('# Обновить все записи (предварительный просмотр):')
        self.stdout.write('docker-compose exec web python manage.py update_vet_durations --dry-run')
        self.stdout.write('')
        self.stdout.write('# Обновить только вакцинации:')
        self.stdout.write('docker-compose exec web python manage.py update_vet_durations --care-type "Вакцинация" --dry-run')
        self.stdout.write('')
        self.stdout.write('# Обновить записи за последний месяц:')
        self.stdout.write('docker-compose exec web python manage.py update_vet_durations --after-date "2026-03-01" --dry-run')
        self.stdout.write('')
        self.stdout.write('# Применить изменения (без --dry-run):')
        self.stdout.write('docker-compose exec web python manage.py update_vet_durations')