"""Seed sample property bookings for Phase 5."""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Role, User, UserProfile
from bookings.models import BookingMode, BookingStatus, PropertyBooking
from listings.models import Property


class Command(BaseCommand):
    help = 'Seed sample property bookings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete existing seeded bookings first',
        )

    def handle(self, *args, **options):
        renter, _ = User.objects.get_or_create(
            phone='+8801710000001',
            defaults={
                'name': 'Rahim Uddin',
                'role': Role.RENTER,
                'role_selected': True,
                'is_phone_verified': True,
            },
        )
        UserProfile.objects.get_or_create(user=renter)

        props = list(
            Property.objects.filter(
                published=True,
                available=True,
            ).select_related('owner')[:2],
        )
        if not props:
            self.stdout.write(self.style.WARNING('No published properties found. Run seed_listings first.'))
            return

        if options['flush']:
            PropertyBooking.objects.filter(
                renter=renter,
                property__in=props,
            ).delete()

        move_in = timezone.now().date() + timedelta(days=14)
        created = 0
        for idx, prop in enumerate(props):
            owner = prop.owner
            rent = Decimal(prop.rent)
            deposit = rent * Decimal(prop.deposit_months or 1)
            duration = 1
            total = rent * duration + deposit
            image = (prop.image_urls or [''])[0]

            instant = prop.instant_book and idx == 1
            status = BookingStatus.APPROVED if instant else BookingStatus.PENDING
            mode = BookingMode.INSTANT if instant else BookingMode.REQUEST

            existing = PropertyBooking.objects.filter(
                property=prop,
                renter=renter,
                is_deleted=False,
                status__in=[BookingStatus.PENDING, BookingStatus.APPROVED],
            ).first()
            if existing:
                booking = existing
                was_created = False
            else:
                booking = PropertyBooking(
                    property=prop,
                    renter=renter,
                )
                was_created = True

            for field, value in {
                'owner': owner,
                'property_name': prop.name,
                'property_type': prop.type,
                'property_address': prop.address,
                'property_image': image,
                'renter_name': renter.name or f'User {renter.phone[-4:]}',
                'renter_phone': renter.phone,
                'renter_email': renter.email or '',
                'owner_name': owner.name or f'User {owner.phone[-4:]}',
                'owner_phone': owner.phone,
                'status': status,
                'booking_mode': mode,
                'move_in_date': move_in,
                'duration': duration,
                'rent': rent,
                'deposit': deposit,
                'total_amount': total,
                'message': 'Looking forward to moving in.',
                'approved_at': timezone.now() if instant else None,
            }.items():
                setattr(booking, field, value)
            booking.save()
            if was_created:
                created += 1
            self.stdout.write(f'  {booking.property_name} → {booking.id} ({booking.status})')

        self.stdout.write(
            self.style.SUCCESS(f'Seeded bookings complete ({created} new).'),
        )
