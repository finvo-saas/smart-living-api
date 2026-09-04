"""Create Bangladesh demo owners, renters, and profiles."""

from django.core.management.base import BaseCommand

from accounts.models import Role
from core.seed_catalog import OWNERS, RENTERS, ensure_user
from subscriptions.services import ensure_default_plans, get_or_create_owner_subscription


class Command(BaseCommand):
    help = 'Seed realistic Bangladesh owner and renter accounts (stable demo phones).'

    def handle(self, *args, **options):
        ensure_default_plans()
        for spec in OWNERS:
            user = ensure_user(
                phone=spec['phone'],
                name=spec['name'],
                role=Role.OWNER,
                email=spec.get('email', ''),
                locale=spec.get('locale', 'bn'),
            )
            get_or_create_owner_subscription(user)
            self.stdout.write(f'  owner {user.phone}  {user.name}')

        for spec in RENTERS:
            user = ensure_user(
                phone=spec['phone'],
                name=spec['name'],
                role=Role.RENTER,
                email=spec.get('email', ''),
                locale=spec.get('locale', 'bn'),
                job_info=spec.get('job_info'),
            )
            self.stdout.write(f'  renter {user.phone}  {user.name}')

        self.stdout.write(self.style.SUCCESS('Seeded Bangladesh users.'))
