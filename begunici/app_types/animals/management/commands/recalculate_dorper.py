from django.core.management.base import BaseCommand
from django.db import transaction
from begunici.app_types.animals.dorper import recalculate_dorper_values
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

        with transaction.atomic():
            changes = recalculate_dorper_values((Maker, Ram, Ewe, Sheep), dry_run=dry_run)
        for change in changes:
            old = f"{change['old']}%" if change['old'] is not None else "Не указано"
            source = "с допущением 50%" if change["uses_default"] else "по родителям"
            self.stdout.write(
                f"{change['model']} {change['tag_number']}: {old} -> {change['new']}% ({source})"
            )
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'\nВсего было бы обновлено: {len(changes)} животных')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nВсего обновлено: {len(changes)} животных')
            )
