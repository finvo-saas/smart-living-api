import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate VAPID keys for Web Push and print .env lines.'

    def handle(self, *args, **options):
        key = ec.generate_private_key(ec.SECP256R1())
        private_raw = key.private_numbers().private_value.to_bytes(32, 'big')
        public_raw = key.public_key().public_bytes(
            Encoding.X962,
            PublicFormat.UncompressedPoint,
        )
        public_b64 = base64.urlsafe_b64encode(public_raw).rstrip(b'=').decode()
        private_b64 = base64.urlsafe_b64encode(private_raw).rstrip(b'=').decode()
        self.stdout.write('Add these to smart-living-api/.env:\n')
        self.stdout.write(f'VAPID_PUBLIC_KEY={public_b64}')
        self.stdout.write(f'VAPID_PRIVATE_KEY={private_b64}')
        self.stdout.write('VAPID_SUBJECT=mailto:support@yourdomain.com')
        self.stdout.write('PUSH_ENABLED=true')
