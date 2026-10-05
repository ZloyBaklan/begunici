"""Read-only reconciliation bridge. Never repairs core or warehouse records."""
import hashlib

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from ...bridges import validate_case_source
from ...models import AnimalCase, DocumentVersion, StockLot
from ...stock import balance


class Command(BaseCommand):
    help = "Проверить складские остатки и связь с архивом без изменения данных."

    def add_arguments(self, parser):
        parser.add_argument("--files", action="store_true", help="Также проверить SHA-256 всех версий файлов.")

    def handle(self, *args, **options):
        problems = []
        for case in AnimalCase.objects.all().iterator():
            try:
                validate_case_source(case)
            except ValidationError as exc:
                problems.append(f"Животное {case.tag_number}: {' '.join(exc.messages)}")
        for lot in StockLot.objects.select_related("product").iterator():
            weight, quantity = balance(lot)
            if weight < 0 or quantity < 0 or (lot.product.counted and (weight == 0) != (quantity == 0)):
                problems.append(f"Партия {lot.pk}: несогласованный остаток {weight} кг / {quantity} шт.")
        if options["files"]:
            for version in DocumentVersion.objects.all().iterator(chunk_size=10):
                if hashlib.sha256(bytes(version.content)).hexdigest() != version.sha256:
                    problems.append(f"Документ {version.document_id}, версия {version.number}: SHA-256 не совпадает.")
        if problems:
            for problem in problems:
                self.stderr.write(problem)
            raise CommandError(f"Найдены расхождения: {len(problems)}. Данные не изменены.")
        self.stdout.write(self.style.SUCCESS("Расхождений не найдено. Данные не изменены."))
