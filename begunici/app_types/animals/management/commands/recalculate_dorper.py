from django.core.management.base import BaseCommand
from begunici.app_types.animals.models import Maker, Ram, Ewe, Sheep


class Command(BaseCommand):
    help = 'Пересчитывает дорперность для всех животных, у которых она не задана вручную'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет изменено, но не сохранять изменения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('РЕЖИМ ТЕСТИРОВАНИЯ - изменения не будут сохранены'))
        
        total_updated = 0
        
        # Обрабатываем все типы животных
        for model in [Maker, Ram, Ewe, Sheep]:
            model_name = model.__name__
            self.stdout.write(f'\n=== Обработка {model_name} ===')
            
            # Находим животных без ручной дорперности
            animals = model.objects.filter(is_manual_dorper=False)
            updated_count = 0
            
            for animal in animals:
                old_dorper = animal.dorper_percentage
                
                # Вызываем расчет
                animal.calculate_dorper_percentage()
                new_dorper = animal.dorper_percentage
                
                # Проверяем, изменилось ли значение
                if old_dorper != new_dorper:
                    if not dry_run:
                        # Сохраняем без вызова полного save() чтобы избежать лишних операций
                        model.objects.filter(id=animal.id).update(
                            dorper_percentage=new_dorper
                        )
                    
                    updated_count += 1
                    total_updated += 1
                    
                    old_str = f"{old_dorper}%" if old_dorper else "None"
                    new_str = f"{new_dorper}%" if new_dorper else "None"
                    
                    self.stdout.write(
                        f"  {animal.tag.tag_number}: {old_str} → {new_str}"
                    )
            
            if updated_count == 0:
                self.stdout.write(f"  Нет изменений для {model_name}")
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"  Обновлено {updated_count} {model_name}")
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'\nВсего было бы обновлено: {total_updated} животных')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nВсего обновлено: {total_updated} животных')
            )