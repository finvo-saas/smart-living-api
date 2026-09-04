"""Run Phase 9 background jobs on demand (works in eager or worker mode)."""

from django.core.management.base import BaseCommand

from billing.tasks import mark_overdue_bills
from discovery.services.freshness import expire_featured
from reports.tasks import dispatch_due_reminders


class Command(BaseCommand):
    help = 'Run overdue-bill + reminder dispatch tasks once'

    def handle(self, *args, **options):
        overdue = mark_overdue_bills()
        reminders = dispatch_due_reminders()
        expired = expire_featured()
        self.stdout.write(
            self.style.SUCCESS(
                f'overdue={overdue} reminders={reminders} expired_featured={expired}',
            ),
        )
