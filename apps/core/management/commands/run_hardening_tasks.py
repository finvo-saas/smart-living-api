"""Run Phase 9 background jobs on demand (works in eager or worker mode)."""

from django.core.management.base import BaseCommand

from billing.tasks import mark_overdue_bills, run_bill_generation_rules
from discovery.services.freshness import expire_featured
from reports.tasks import dispatch_due_reminders


class Command(BaseCommand):
    help = 'Run overdue-bill, bill-rule, and reminder dispatch tasks once'

    def handle(self, *args, **options):
        overdue = mark_overdue_bills()
        rules = run_bill_generation_rules()
        reminders = dispatch_due_reminders()
        expired = expire_featured()
        self.stdout.write(
            self.style.SUCCESS(
                f'overdue={overdue} rules={rules} '
                f'reminders={reminders} expired_featured={expired}',
            ),
        )
