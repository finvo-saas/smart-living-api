"""Seed demo admin phones matching frontend DEMO_ADMIN_PHONES."""

from django.core.management.base import BaseCommand

from accounts.models import AdminProfile, Role, User, UserProfile
from accounts.phone import normalize_bd_phone

# System login only. Django /admin/ stays on the existing superuser password.
DEMO_ADMINS = [
    ('01934856451', AdminProfile.AdminRole.SUPER_ADMIN, 'Super Admin'),
]
RETIRED_SYSTEM_ADMINS = [
    '+8801711111111',
    '+8801722222222',
    '+8801733333333',
    '+88019134856451',
]


class Command(BaseCommand):
    help = 'Create demo AdminProfile users for local development'

    def handle(self, *args, **options):
        for raw_phone, admin_role, name in DEMO_ADMINS:
            phone = normalize_bd_phone(raw_phone)
            user, created = User.objects.get_or_create(
                phone=phone,
                defaults={
                    'name': name,
                    'role': Role.ADMIN,
                    'role_selected': True,
                    'is_phone_verified': True,
                    'is_staff': True,
                    'is_superuser': True,
                    'is_active': True,
                },
            )
            user.name = user.name or name
            user.role = Role.ADMIN
            user.role_selected = True
            user.is_phone_verified = True
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()
            UserProfile.objects.get_or_create(user=user)
            profile, _p_created = AdminProfile.objects.update_or_create(
                user=user,
                defaults={'admin_role': admin_role, 'is_active': True},
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(
                self.style.SUCCESS(
                    f'{action} admin {user.phone} -> {profile.admin_role}',
                ),
            )

        retired = AdminProfile.objects.filter(
            user__phone__in=RETIRED_SYSTEM_ADMINS,
            is_active=True,
        ).update(is_active=False)
        if retired:
            self.stdout.write(
                self.style.WARNING(
                    f'Deactivated {retired} unused demo system admin profile(s).',
                ),
            )
