"""Show the active object-storage config and optionally round-trip a file.

    python manage.py storage_check
    python manage.py storage_check --write
"""

import base64
import io
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from core.services.media import KIND_RULES, media_storage

# 1x1 transparent PNG.
PROBE_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8'
    '/x8AAwMCAO+ip1sAAAAASUVORK5CYII=',
)


class Command(BaseCommand):
    help = 'Print storage provider/bucket/folder layout; --write round-trips a probe file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--write',
            action='store_true',
            help='Upload, read back, and delete a probe file (real network call).',
        )
        parser.add_argument(
            '--kind',
            default='property',
            help='Kind to probe with --write (default: property).',
        )

    def handle(self, *args, **options):
        info = media_storage.describe()
        self.stdout.write(self.style.MIGRATE_HEADING('Object storage'))
        for label in ('provider', 'object_storage', 'bucket', 'endpoint',
                      'public_domain', 'root_folder'):
            self.stdout.write(f'  {label:<16} {info[label] or "—"}')

        self.stdout.write(self.style.MIGRATE_HEADING('Folders by upload kind'))
        for kind, path in info['folders'].items():
            marker = ' (private)' if KIND_RULES[kind].private else ''
            self.stdout.write(f'  {kind:<16} {path}/{marker}')

        if not options['write']:
            return

        if not info['object_storage']:
            raise CommandError(
                'Object storage is off — set DO_SPACES_* keys before --write.',
            )

        kind = options['kind']
        probe = SimpleUploadedFile('storage-check.png', PROBE_PNG, 'image/png')
        stored = media_storage.upload(probe, kind)
        self.stdout.write(self.style.MIGRATE_HEADING('Round trip'))
        self.stdout.write(f'  uploaded         {stored.key}')
        self.stdout.write(f'  url              {stored.url}')

        backend = media_storage.backend(private=stored.private)
        with backend.open(stored.key) as handle:
            read_back = io.BytesIO(handle.read()).getvalue()
        if read_back != PROBE_PNG:
            raise CommandError('Read-back mismatch — check bucket permissions.')
        self.stdout.write(f'  read back        {len(read_back)} bytes OK')
        self.stdout.write(f'  url fetch        {self._fetch_status(stored.url)}')

        media_storage.delete(stored.key, private=stored.private)
        still_there = backend.exists(stored.key)
        self.stdout.write(f'  deleted          {not still_there}')
        if still_there:
            raise CommandError('Probe file could not be deleted.')
        self.stdout.write(self.style.SUCCESS('Storage round trip OK.'))

    def _fetch_status(self, url: str) -> str:
        """Confirm the returned URL is actually readable (CDN or signed link)."""
        if not url.startswith('http'):
            return f'skipped (local URL {url})'
        try:
            with urlopen(url, timeout=15) as response:  # noqa: S310 - our own URL
                return f'HTTP {response.status}'
        except HTTPError as exc:
            return f'HTTP {exc.code}'
        except URLError as exc:
            return f'unreachable ({exc.reason})'
