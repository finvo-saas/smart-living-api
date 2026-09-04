from django.core.management.base import BaseCommand

from discovery.services.heartbeat import run_heartbeat_batch


class Command(BaseCommand):
    help = 'Send vacancy heartbeat SMS/links to owners (respects admin config).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Ignore jobEnabled and weekday/hour window.',
        )
        parser.add_argument(
            '--sms',
            action='store_true',
            help='Attempt live SMS (still requires HEARTBEAT_SMS_ENABLED=true).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Create pings and links but do not send SMS.',
        )

    def handle(self, *args, **options):
        send_override = None
        if options['dry_run']:
            send_override = False
        elif options['sms']:
            send_override = True
        result = run_heartbeat_batch(
            force=bool(options['force']),
            send_sms_override=send_override,
        )
        self.stdout.write(self.style.SUCCESS(str(result)))
