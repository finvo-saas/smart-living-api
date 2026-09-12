"""Index existing owner uploads into the per-owner media library."""

from django.core.management.base import BaseCommand

from core.services.media_library import backfill_owner_media


class Command(BaseCommand):
    help = 'Create MediaAsset rows for photos already stored on messes, listings, and hotels.'

    def handle(self, *args, **options):
        created = backfill_owner_media()
        self.stdout.write(self.style.SUCCESS(f'Indexed {created} owner media file(s).'))
