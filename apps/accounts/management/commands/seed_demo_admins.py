"""Seed demo admin phones matching frontend DEMO_ADMIN_PHONES."""

from django.core.management.base import BaseCommand

from accounts.models import AdminProfile, Role, User, UserProfile


DEMO_ADMINS = [
    ('+8801711111111', 'super-admin', 'Super Admin'),
    ('+8801722222222', 'moderator', 'Moderator'),
    ('+8801733333333', 'support', 'Support Agent'),
]


class Command(BaseCommand):
    help = 'Create demo AdminProfile users for local development'

    def handle(self, *args, **options):
        for phone, admin_role, name in DEMO_ADMINS:
            user, created = User.objects.get_or_create(
                phone=phone,
                defaults={
                    'name': name,
                    'role': Role.ADMIN,
                    'role_selected': True,
                    'is_phone_verified': True,
                    'is_staff': True,
                },
            )
            UserProfile.objects.get_or_create(user=user)
            profile, p_created = AdminProfile.objects.update_or_create(
                user=user,
                defaults={'admin_role': admin_role, 'is_active': True},
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(
                self.style.SUCCESS(
                    f'{action} admin {phone} -> {profile.admin_role}',
                ),
            )
