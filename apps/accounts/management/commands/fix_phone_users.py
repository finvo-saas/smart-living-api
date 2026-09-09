"""
Normalize Bangladesh phones, merge duplicate accounts, assign demo roles.

Usage:
  python manage.py fix_phone_users
  python manage.py fix_phone_users --dry-run
"""
from __future__ import annotations

from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from accounts.models import AdminProfile, Role, User, UserProfile
from accounts.phone import normalize_bd_phone
from core.exceptions import InvalidError


# Canonical demo accounts requested by product owner
ROLE_PHONES = {
    Role.RENTER: '01991166550',
    Role.OWNER: '01917161352',
    Role.ADMIN: '01934856451',
}


def _digits(raw: str) -> str:
    return ''.join(ch for ch in str(raw) if ch.isdigit())


def _last10(raw: str) -> str:
    d = _digits(raw)
    return d[-10:] if len(d) >= 10 else d


def _score_user(user: User) -> tuple:
    """Prefer verified named accounts with relations over bare duplicates."""
    rel = 0
    for field in user._meta.get_fields():
        if not field.is_relation or field.many_to_one:
            continue
        if field.auto_created and not field.concrete:
            continue
        try:
            related = getattr(user, field.get_accessor_name(), None)
            if related is None:
                continue
            if hasattr(related, 'count'):
                rel += related.count()
            else:
                rel += 1
        except Exception:
            continue
    return (
        1 if user.is_phone_verified else 0,
        1 if (user.name or '').strip() else 0,
        1 if user.role_selected else 0,
        rel,
        1 if user.phone.startswith('+880') and ' ' not in user.phone else 0,
        str(user.created_at),
    )


class Command(BaseCommand):
    help = 'Normalize phones, merge duplicates, set renter/owner/admin demo accounts.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show actions without writing.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        if dry:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes saved'))

        with transaction.atomic():
            self._normalize_all(dry)
            self._merge_duplicates(dry)
            self._ensure_role_accounts(dry)
            if dry:
                transaction.set_rollback(True)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Current role phones:'))
        for role, raw in ROLE_PHONES.items():
            phone = normalize_bd_phone(raw)
            user = User.objects.filter(phone=phone).first()
            if user:
                self.stdout.write(
                    f'  {role:7} {user.phone}  name={user.name!r} '
                    f'staff={user.is_staff} active={user.is_active}',
                )
            else:
                self.stdout.write(self.style.ERROR(f'  {role:7} MISSING {phone}'))

        self.stdout.write('')
        self.stdout.write('Remaining duplicate last-10 groups:')
        groups = defaultdict(list)
        for u in User.objects.all():
            groups[_last10(u.phone)].append(u)
        found = False
        for key, users in sorted(groups.items()):
            if len(users) > 1:
                found = True
                self.stdout.write(f'  ...{key}: {[u.phone for u in users]}')
        if not found:
            self.stdout.write(self.style.SUCCESS('  none'))

    def _normalize_all(self, dry: bool):
        self.stdout.write('Normalizing phone strings...')
        for user in list(User.objects.all()):
            try:
                canonical = normalize_bd_phone(user.phone)
            except InvalidError:
                self.stdout.write(
                    self.style.ERROR(f'  skip invalid phone {user.phone!r} id={user.id}'),
                )
                continue
            if user.phone == canonical:
                continue
            clash = User.objects.filter(phone=canonical).exclude(pk=user.pk).first()
            if clash:
                self.stdout.write(
                    f'  defer normalize {user.phone!r} -> {canonical} '
                    f'(clash with {clash.id}, will merge)',
                )
                continue
            self.stdout.write(f'  {user.phone!r} -> {canonical}')
            if not dry:
                user.phone = canonical
                user.save(update_fields=['phone', 'updated_at'])

    def _merge_duplicates(self, dry: bool):
        self.stdout.write('Merging duplicates by last 10 digits...')
        groups = defaultdict(list)
        for user in User.objects.all():
            groups[_last10(user.phone)].append(user)

        for key, users in sorted(groups.items()):
            if len(users) < 2:
                continue
            users_sorted = sorted(users, key=_score_user, reverse=True)
            keeper = users_sorted[0]
            try:
                target_phone = normalize_bd_phone(keeper.phone)
            except InvalidError:
                target_phone = normalize_bd_phone(f'0{key}' if len(key) == 10 else key)

            self.stdout.write(
                f'  group ...{key}: keep {keeper.phone!r} ({keeper.role}) '
                f'as {target_phone}; drop {[u.phone for u in users_sorted[1:]]}',
            )
            if dry:
                continue

            for dup in users_sorted[1:]:
                self._reassign_user_fks(dup, keeper)
                dup.delete()

            if keeper.phone != target_phone:
                clash = User.objects.filter(phone=target_phone).exclude(pk=keeper.pk).first()
                if clash:
                    self._reassign_user_fks(clash, keeper)
                    clash.delete()
                keeper.phone = target_phone
                keeper.save(update_fields=['phone', 'updated_at'])

    def _reassign_user_fks(self, source: User, target: User):
        """Move FK/OneToOne relations from source -> target where possible."""
        for field in source._meta.get_fields():
            if not field.auto_created or field.concrete:
                continue
            accessor = field.get_accessor_name()
            related = getattr(source, accessor, None)
            if related is None:
                continue

            # OneToOne reverse
            if field.one_to_one:
                try:
                    obj = related
                except Exception:
                    continue
                # If target already has the same OneToOne, drop source's
                remote_field = field.field
                filter_kwargs = {remote_field.name: target}
                model = obj.__class__
                if model.objects.filter(**filter_kwargs).exists():
                    obj.delete()
                else:
                    setattr(obj, remote_field.name, target)
                    obj.save(update_fields=[remote_field.name])
                continue

            # Reverse FK / M2M related manager
            if not hasattr(related, 'all'):
                continue
            remote_field = field.field
            for obj in list(related.all()):
                try:
                    setattr(obj, remote_field.name, target)
                    obj.save(update_fields=[remote_field.name])
                except Exception:
                    # Unique conflicts etc. — delete the duplicate relation
                    try:
                        obj.delete()
                    except Exception:
                        pass

        # Explicit high-value FKs that may use different field names
        Mess = apps.get_model('mess', 'Mess')
        Mess.objects.filter(owner=source).update(owner=target)
        # Keep owner_phone in sync when merging into owner account
        Mess.objects.filter(owner=target).update(owner_phone=target.phone)

    def _ensure_role_accounts(self, dry: bool):
        self.stdout.write('Ensuring requested role accounts...')
        specs = [
            (Role.RENTER, ROLE_PHONES[Role.RENTER], 'Demo Renter', False, False),
            (Role.OWNER, ROLE_PHONES[Role.OWNER], 'Demo Owner', False, False),
            (Role.ADMIN, ROLE_PHONES[Role.ADMIN], 'Demo Admin', True, True),
        ]
        for role, raw, name, staff, superuser in specs:
            phone = normalize_bd_phone(raw)
            user = User.objects.filter(phone=phone).first()
            created = False
            if user is None:
                created = True
                self.stdout.write(f'  create {role} {phone}')
                if dry:
                    continue
                user = User(
                    phone=phone,
                    name=name,
                    role=role,
                    role_selected=True,
                    is_phone_verified=True,
                    is_active=True,
                    is_staff=staff,
                    is_superuser=superuser,
                )
                user.set_unusable_password()
                user.save()
            else:
                self.stdout.write(
                    f'  update {user.phone} -> role={role} '
                    f'(was {user.role}, created={created})',
                )
                if dry:
                    continue
                user.role = role
                user.role_selected = True
                user.is_phone_verified = True
                user.is_active = True
                user.is_staff = staff
                user.is_superuser = superuser
                if not (user.name or '').strip():
                    user.name = name
                user.save()

            UserProfile.objects.get_or_create(user=user)
            if role == Role.ADMIN:
                profile, _ = AdminProfile.objects.get_or_create(user=user)
                if profile.admin_role != AdminProfile.AdminRole.SUPER_ADMIN:
                    profile.admin_role = AdminProfile.AdminRole.SUPER_ADMIN
                    profile.is_active = True
                    profile.save(update_fields=['admin_role', 'is_active', 'updated_at'])
            elif hasattr(user, 'admin_profile'):
                # Non-admins should not keep admin profile privileges
                user.admin_profile.is_active = False
                user.admin_profile.save(update_fields=['is_active', 'updated_at'])

            if role == Role.OWNER:
                Mess = apps.get_model('mess', 'Mess')
                # Point seeded Green Valley–style ownership phones to this owner when empty FK
                updated = Mess.objects.filter(owner=user).update(owner_phone=phone)
                # Also attach messes previously owned by duplicate variants
                Mess.objects.filter(owner_phone__in=[raw, phone, f'+880 {raw[1:]}']).update(
                    owner=user,
                    owner_phone=phone,
                )
                self.stdout.write(f'    mess owner_phone sync (touched rows ok)')
