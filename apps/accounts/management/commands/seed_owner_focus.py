"""Assign each demo owner a clear business focus (mess / apartment / hotel).

Rules:
- Every owner gets at least one vertical.
- Owners may have one or all verticals.
- Mess-primary demo owner stays mess-only (no hotels / buildings).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from accounts.models import Role, User
from hotels.models import Hotel
from mess.models import Mess
from portfolio.models import Building


# Canonical demo owner phones (E.164). Also accept remapped product phones.
MESS_ONLY_PHONES = {
    '+8801712345678',  # catalog Abdul Karim
    '+8801917161352',  # product remapped Abdul Karim (fix_phone_users)
    '+8801712345681',  # Shahidul — Mohammadpur Campus Mess
    '+8801812345678',  # Nusrat — Uttara Tech Mess
}

HOTEL_ONLY_PHONES = {
    '+8801512345678',  # Tanvir
    '+8801912345678',  # Rafiq
}

APARTMENT_ONLY_PHONES = {
    '+8801712345680',  # Karim Hossain — Green Valley building
    '+8801612345678',  # Mahmuda — apartment focus (may get building if empty)
}

# Fatima keeps mess + apartment (multi)
MULTI_PHONES = {
    '+8801712345679': ['mess', 'apartment'],
}


def _normalize_owner_phone_set() -> dict[str, User]:
    owners = {}
    for u in User.objects.filter(role=Role.OWNER):
        owners[u.phone] = u
    return owners


class Command(BaseCommand):
    help = (
        'Rebalance demo ownership and set owner_enabled_verticals / primary focus '
        'so dashboards stay focused.'
    )

    def handle(self, *args, **options):
        by_phone = _normalize_owner_phone_set()

        mess_owner = (
            by_phone.get('+8801917161352')
            or by_phone.get('+8801712345678')
        )
        hotel_primary = by_phone.get('+8801512345678')
        hotel_secondary = by_phone.get('+8801912345678')
        apartment_owner = by_phone.get('+8801712345680')
        mahmuda = by_phone.get('+8801612345678')

        # --- Reassign hotels away from mess-only Abdul ---
        if mess_owner and hotel_primary:
            hotels = Hotel.objects.filter(owner=mess_owner)
            count = hotels.count()
            if count:
                # Split: first half Tanvir, rest Rafiq (or all Tanvir)
                ids = list(hotels.values_list('id', flat=True))
                mid = max(1, len(ids) // 2) if hotel_secondary else len(ids)
                Hotel.objects.filter(id__in=ids[:mid]).update(
                    owner=hotel_primary,
                    owner_phone=hotel_primary.phone,
                    owner_name=hotel_primary.name or hotel_primary.phone,
                )
                if hotel_secondary and ids[mid:]:
                    Hotel.objects.filter(id__in=ids[mid:]).update(
                        owner=hotel_secondary,
                        owner_phone=hotel_secondary.phone,
                        owner_name=hotel_secondary.name or hotel_secondary.phone,
                    )
                self.stdout.write(
                    f'  moved {count} hotel(s) off {mess_owner.phone}',
                )

        # Ensure seeded Dhaka hotels point at hotel specialists
        if hotel_primary:
            Hotel.objects.filter(name='Grand Plaza Hotel Dhaka').update(
                owner=hotel_primary,
                owner_phone=hotel_primary.phone,
                owner_name=hotel_primary.name or '',
            )
        if hotel_secondary:
            Hotel.objects.filter(
                name__in=['Comfort Guest House', 'Hotel 71 Motijheel'],
            ).update(
                owner=hotel_secondary,
                owner_phone=hotel_secondary.phone,
                owner_name=hotel_secondary.name or '',
            )

        # --- Reassign Green Valley building to apartment owner ---
        if apartment_owner:
            moved = Building.objects.filter(name='Green Valley').update(
                owner=apartment_owner,
            )
            if mess_owner:
                Building.objects.filter(owner=mess_owner).exclude(
                    name='Green Valley',
                ).update(owner=apartment_owner)
            self.stdout.write(
                f'  Green Valley building -> {apartment_owner.phone} '
                f'(rows={moved})',
            )

        # Mahmuda needs at least one vertical — give a building if she has none
        if mahmuda and apartment_owner:
            has_anything = (
                Mess.objects.filter(owner=mahmuda, is_deleted=False).exists()
                or Hotel.objects.filter(owner=mahmuda).exists()
                or Building.objects.filter(owner=mahmuda).exists()
            )
            if not has_anything:
                Building.objects.update_or_create(
                    owner=mahmuda,
                    name='Mahmuda Residence',
                    defaults={
                        'address': 'House 12, Road 3, Mirpur-1',
                        'city': 'Dhaka',
                        'total_floors': 1,
                        'total_flats': 2,
                    },
                )
                self.stdout.write(f'  created apartment seed for {mahmuda.phone}')

        # --- Apply focus from actual ownership + forced singles ---
        for user in User.objects.filter(role=Role.OWNER):
            verticals: list[str] = []
            if Mess.objects.filter(
                Q(owner=user) | Q(owner_phone=user.phone),
                is_deleted=False,
            ).exists():
                verticals.append('mess')
            if Building.objects.filter(owner=user).exists():
                verticals.append('apartment')
            if Hotel.objects.filter(
                Q(owner=user) | Q(owner_phone=user.phone),
            ).exists():
                verticals.append('hotel')

            # Force intended singles even if inference drifted
            if user.phone in MESS_ONLY_PHONES:
                verticals = ['mess'] if 'mess' in verticals or Mess.objects.filter(
                    Q(owner=user) | Q(owner_phone=user.phone),
                    is_deleted=False,
                ).exists() else verticals
                # If still empty, keep mess flag for Green Valley owner
                if user.phone in {'+8801917161352', '+8801712345678'}:
                    verticals = ['mess']
            elif user.phone in HOTEL_ONLY_PHONES:
                verticals = ['hotel'] if 'hotel' in verticals else (
                    ['hotel'] if Hotel.objects.filter(owner=user).exists() else verticals
                )
                if not verticals:
                    verticals = ['hotel']
            elif user.phone in APARTMENT_ONLY_PHONES:
                verticals = ['apartment'] if 'apartment' in verticals else (
                    ['apartment'] if Building.objects.filter(owner=user).exists() else ['apartment']
                )
            elif user.phone in MULTI_PHONES:
                verticals = MULTI_PHONES[user.phone]

            if not verticals:
                # Last resort: apartment so owner can still use the app
                verticals = ['apartment']

            # Deduplicate preserve order
            seen = set()
            ordered = []
            for v in verticals:
                if v not in seen:
                    seen.add(v)
                    ordered.append(v)

            user.owner_enabled_verticals = ordered
            user.owner_primary_focus = ordered[0]
            user.owner_focus_selected = True
            user.save(
                update_fields=[
                    'owner_enabled_verticals',
                    'owner_primary_focus',
                    'owner_focus_selected',
                    'updated_at',
                ],
            )
            self.stdout.write(
                f'  {user.phone}  {user.name}: {ordered} (primary={ordered[0]})',
            )

        self.stdout.write(self.style.SUCCESS('Owner business focus seeded.'))
        self.stdout.write('')
        self.stdout.write('Demo logins (OTP from SMS / DEBUG):')
        self.stdout.write('  Mess owner     +8801917161352  Abdul Karim (Green Valley Mess)')
        self.stdout.write('  Mess owner     +8801712345681  Shahidul Islam')
        self.stdout.write('  Apartment      +8801712345680  Karim Hossain')
        self.stdout.write('  Hotel          +8801512345678  Tanvir Hasan')
        self.stdout.write('  Multi (mess+)  +8801712345679  Fatima Begum')
