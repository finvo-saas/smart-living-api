"""Manually run (or dry-run) bill automation rules."""

from django.core.management.base import BaseCommand

from billing.services.scheduler import run_due_bill_rules


class Command(BaseCommand):
    help = (
        'Run due bill generation rules now. '
        'Use --dry-run to preview without creating bills.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show which rules would run without creating bills.',
        )
        parser.add_argument(
            '--rule-id',
            type=str,
            default=None,
            help='Only process one rule UUID.',
        )

    def handle(self, *args, **options):
        result = run_due_bill_rules(
            dry_run=options['dry_run'],
            rule_id=options['rule_id'],
        )
        self.stdout.write(self.style.SUCCESS(
            f"asOf={result['asOf']} rules={result['rulesProcessed']} "
            f"bills={result['billsCreated']} dryRun={result['dryRun']}"
        ))
        for row in result.get('results') or []:
            self.stdout.write(
                f"  - {row.get('ruleName')} "
                f"cycles={row.get('cycles')} "
                f"bills={row.get('billsCreated')} "
                f"skipped={row.get('skipped')} "
                f"{row.get('reason') or ''}"
            )
