"""Run every domain seed in dependency order with Bangladesh demo data."""

import sys

from django.core.management import call_command
from django.core.management.base import BaseCommand


SEED_STEPS = [
    'seed_demo_admins',
    'seed_users',
    'seed_listings',
    'seed_hotels',
    'seed_portfolio',
    'seed_mess',
    'seed_bookings',
    'seed_payments',
    'seed_renter_tools',
    'seed_admin_tools',
    'seed_relations',
    'seed_owner_focus',
    'seed_complete',
]


class Command(BaseCommand):
    help = (
        'Seed the full SmartBasa catalog: users, listings, hotels, mess, '
        'portfolio, bills, bookings, chats, and admin tools.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help=(
                'Flush listings/hotels/mess/bookings before reseeding '
                '(idempotent seeds still update).'
            ),
        )

    def handle(self, *args, **options):
        # Windows consoles often use cp1252; avoid UnicodeEncodeError on seed logs.
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, 'reconfigure', None)
            if callable(reconfigure):
                try:
                    reconfigure(encoding='utf-8', errors='replace')
                except Exception:
                    pass

        flush = bool(options.get('flush'))
        for name in SEED_STEPS:
            self.stdout.write(self.style.MIGRATE_HEADING(f'>> {name}'))
            kwargs = {}
            if flush and name in {
                'seed_listings',
                'seed_hotels',
                'seed_mess',
                'seed_bookings',
            }:
                kwargs['flush'] = True
            call_command(name, **kwargs)
        self.stdout.write(self.style.SUCCESS('All Bangladesh seeds finished.'))
        self.stdout.write(
            'Login phones (OTP 123456 in DEBUG; PIN 1234 after seed_complete):',
        )
        self.stdout.write('  Super admin     +8801711111111')
        self.stdout.write('  Mess owner      +8801917161352  Abdul Karim (Green Valley)')
        self.stdout.write('  Apartment owner +8801917161305  Karim Hossain (preferred)')
        self.stdout.write('  Apartment owner +8801712345680  Karim Hossain (catalog)')
        self.stdout.write('  Hotel owner     +8801512345678  Tanvir Hasan')
        self.stdout.write('  Renter          +8801710000001  Rahim Uddin')
        self.stdout.write('  (Also remapped renter/admin via fix_phone_users if used.)')
