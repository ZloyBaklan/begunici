import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections

from begunici.app_types.public_site.catalog_sync import SyncError, send_catalogue, sender_config


class Command(BaseCommand):
    help = 'Publish the public catalogue once, or periodically with --watch.'

    def add_arguments(self, parser):
        parser.add_argument('--watch', action='store_true')
        parser.add_argument('--interval', type=int, default=None)

    def handle(self, *args, **options):
        try:
            sender_config()
        except SyncError as exc:
            raise CommandError(str(exc)) from None
        interval = options['interval'] if options['interval'] is not None else settings.CATALOG_SYNC_INTERVAL
        if not 15 <= interval <= 86400:
            raise CommandError('Interval must be between 15 and 86400 seconds')
        while True:
            try:
                if options['watch']:
                    close_old_connections()
                result = send_catalogue()
                self.stdout.write(f"Catalogue {result['status']}: version {result['version']}, products {result['products']}")
            except (SyncError, DatabaseError) as exc:
                message = str(exc) if isinstance(exc, SyncError) else 'Database unavailable; publication not confirmed'
                if not options['watch']:
                    raise CommandError(message) from None
                self.stderr.write(message)
            if not options['watch']:
                return
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                return
