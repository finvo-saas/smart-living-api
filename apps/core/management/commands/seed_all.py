"""Run every domain seed in dependency order with Bangladesh demo data."""

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
]


class Command(BaseCommand):
    help = (
        'Seed the full Smart Living catalog: users, listings, hotels, mess, '
        'portfolio, bills, bookings, chats, and admin tools.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Flush listings/hotels/mess/bookings before reseeding (idempotent seeds still update).',
        )

    def handle(self, *args, **options):
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
        self.stdout.write('Login phones (OTP 123456 in DEBUG):')
        self.stdout.write('  Super admin  +8801711111111')
        self.stdout.write('  Owner        +8801712345678  Abdul Karim')
        self.stdout.write('  Renter       +8801710000001  Rahim Uddin')
