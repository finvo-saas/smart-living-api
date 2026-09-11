"""Fill remaining relations so dashboards show live Bangladesh data."""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Role, User, VerificationDocument
from bookings.models import BookingMode, BookingStatus, PropertyBooking
from discovery.models import Favorite, SavedSearch, SearchHistory
from hotels.models import (
    Hotel,
    HotelBooking,
    HotelBookingStatus,
    HotelReview,
    PaymentMethod as HotelPayMethod,
    PaymentStatus as HotelPayStatus,
)
from listings.models import Property
from messaging.models import Notification, NotificationType
from payments.models import (
    PaymentMethod,
    PaymentSchedule,
    ScheduleFrequency,
    ScheduledPayment,
    ScheduledPaymentStatus,
)
from portfolio.models import Building, Flat, FlatStatus, Floor, Tenancy, TenancyStatus
from portfolio.services.seed_buildings import ensure_building
from billing.models import Bill, BillItem, BillItemType, BillStatus, PropertyKind
from billing.services.generation import default_due_date
from subscriptions.models import FeaturedBoost, PlanTier
from subscriptions.services import get_or_create_owner_subscription


class Command(BaseCommand):
    help = 'Seed favorites, searches, hotel stays, extra tenancies, and bills.'

    def handle(self, *args, **options):
        renters = list(User.objects.filter(role=Role.RENTER, is_active=True).order_by('phone'))
        owners = list(User.objects.filter(role=Role.OWNER, is_active=True))
        properties = list(Property.objects.filter(published=True).select_related('owner'))
        hotels = list(Hotel.objects.filter(is_deleted=False).prefetch_related('rooms'))
        today = timezone.now().date()
        now = timezone.now()

        self._favorites_and_search(renters, properties)
        self._extra_tenancies(renters, today)
        self._property_bookings(renters, properties, today)
        self._hotel_stays(renters, hotels, today)
        self._verifications(renters, owners)
        self._notifications(renters)
        self._boosts(properties, now)
        self._schedules(renters)
        self.stdout.write(self.style.SUCCESS('Relational Bangladesh seed complete.'))

    def _favorites_and_search(self, renters, properties):
        if not renters or not properties:
            return
        for idx, renter in enumerate(renters[:6]):
            for prop in properties[idx : idx + 3]:
                Favorite.objects.get_or_create(
                    user=renter,
                    property=prop,
                    defaults={'notes': f'Saved from search in {prop.city}'},
                )
            SavedSearch.objects.update_or_create(
                user=renter,
                name=f'{renter.name.split()[0]} — Dhaka mess',
                defaults={
                    'filters': {
                        'city': 'Dhaka',
                        'type': 'mess',
                        'maxRent': 5000,
                    },
                    'is_active': True,
                    'match_count': 4,
                    'last_checked': timezone.now(),
                },
            )
            SearchHistory.objects.get_or_create(
                user=renter,
                search_query='mess near university dhaka',
                defaults={
                    'filters': {'city': 'Dhaka', 'type': 'mess'},
                    'result_count': 6,
                },
            )
        self.stdout.write(f'  favorites/searches for {min(6, len(renters))} renters')

    def _extra_tenancies(self, renters, today):
        owner = User.objects.filter(phone='+8801712345679').first()
        sadia = User.objects.filter(phone='+8801710000002').first()
        imran = User.objects.filter(phone='+8801710000003').first()
        if not owner or not sadia:
            return

        building, _ = ensure_building(
            owner=owner,
            name='Uttara Lake View',
            defaults={
                'address': 'House 22, Road 7, Sector 7, Uttara',
                'city': 'Dhaka',
                'total_floors': 3,
                'total_flats': 3,
            },
        )
        floors = {}
        for num in (1, 2, 3):
            floor, _ = Floor.objects.update_or_create(
                building=building,
                floor_number=num,
                defaults={'name': f'Floor {num}'},
            )
            floors[num] = floor

        specs = [
            ('3A', 1, 14000, FlatStatus.OCCUPIED, sadia),
            ('3B', 2, 16000, FlatStatus.OCCUPIED, imran),
            ('3C', 3, 18000, FlatStatus.AVAILABLE, None),
        ]
        for number, floor_num, rent, status, tenant in specs:
            flat, _ = Flat.objects.update_or_create(
                building=building,
                flat_number=number,
                defaults={
                    'floor': floors[floor_num],
                    'floor_number': floor_num,
                    'rent': Decimal(str(rent)),
                    'status': status,
                    'area': 900,
                    'bedrooms': 2,
                    'bathrooms': 2,
                },
            )
            if tenant is None:
                continue
            Tenancy.objects.filter(flat=flat, status=TenancyStatus.ACTIVE).exclude(
                tenant=tenant,
            ).update(status=TenancyStatus.ENDED, end_date=today)
            Tenancy.objects.update_or_create(
                flat=flat,
                tenant=tenant,
                status=TenancyStatus.ACTIVE,
                defaults={
                    'start_date': date(2025, 6, 1),
                    'tenant_name': tenant.name,
                    'tenant_phone': tenant.phone,
                    'tenant_whatsapp': tenant.whatsapp_number or tenant.phone,
                    'tenant_email': tenant.email,
                    'tenant_nid': f'19{tenant.phone[-10:]}',
                    'tenant_address': f'{building.address}',
                    'deposit': Decimal(str(rent * 2)),
                },
            )
            month = today.strftime('%B')
            year = today.year
            bill, _ = Bill.objects.update_or_create(
                owner=owner,
                property_id=building.id,
                flat=flat,
                month=month,
                year=year,
                defaults={
                    'tenant': tenant,
                    'tenant_name': tenant.name,
                    'tenant_id_snapshot': str(tenant.id),
                    'property_type': PropertyKind.APARTMENT,
                    'property_name': building.name,
                    'flat_number': flat.flat_number,
                    'amount': Decimal(str(rent + 800)),
                    'due_date': default_due_date(year, month),
                    'status': BillStatus.UNPAID,
                },
            )
            BillItem.objects.filter(bill=bill).delete()
            BillItem.objects.create(
                bill=bill,
                description='Monthly Rent',
                amount=Decimal(str(rent)),
                type=BillItemType.RENT,
            )
            BillItem.objects.create(
                bill=bill,
                description='Service charge + DESCO',
                amount=Decimal('800'),
                type=BillItemType.UTILITY,
            )

        building.refresh_counts()
        get_or_create_owner_subscription(owner)
        self.stdout.write(f'  extra building {building.name}')

    def _property_bookings(self, renters, properties, today):
        extra = [p for p in properties if p.instant_book or p.type == 'apartment'][:4]
        renter = User.objects.filter(phone='+8801710000004').first()
        if not renter or not extra:
            return
        created = 0
        for idx, prop in enumerate(extra):
            rent = Decimal(prop.rent)
            deposit = rent * Decimal(prop.deposit_months or 1)
            PropertyBooking.objects.update_or_create(
                property=prop,
                renter=renter,
                defaults={
                    'owner': prop.owner,
                    'property_name': prop.name,
                    'property_type': prop.type,
                    'property_address': prop.address,
                    'property_image': (prop.image_urls or [''])[0],
                    'renter_name': renter.name,
                    'renter_phone': renter.phone,
                    'renter_email': renter.email,
                    'owner_name': prop.owner.name,
                    'owner_phone': prop.owner.phone,
                    'status': BookingStatus.APPROVED if idx == 0 else BookingStatus.PENDING,
                    'booking_mode': (
                        BookingMode.INSTANT if prop.instant_book else BookingMode.REQUEST
                    ),
                    'move_in_date': today + timedelta(days=10 + idx * 7),
                    'duration': 6 if prop.type == 'apartment' else 1,
                    'rent': rent,
                    'deposit': deposit,
                    'total_amount': rent + deposit,
                    'message': 'Assalamu alaikum, I would like to visit this week.',
                    'approved_at': timezone.now() if idx == 0 else None,
                },
            )
            created += 1
        self.stdout.write(f'  extra property bookings: {created}')

    def _hotel_stays(self, renters, hotels, today):
        guests = [
            User.objects.filter(phone='+8801710000002').first(),
            User.objects.filter(phone='+8801710000005').first(),
            User.objects.filter(phone='+8801710000006').first(),
        ]
        guests = [g for g in guests if g]
        if not guests or not hotels:
            self.stdout.write(self.style.WARNING('  skip hotel stays (need hotels + renters)'))
            return

        statuses = [
            HotelBookingStatus.COMPLETED,
            HotelBookingStatus.CONFIRMED,
            HotelBookingStatus.PENDING,
        ]
        for idx, hotel in enumerate(hotels[:4]):
            room = hotel.rooms.filter(available=True).first() or hotel.rooms.first()
            if room is None:
                continue
            guest = guests[idx % len(guests)]
            check_in = today - timedelta(days=20 - idx * 5)
            check_out = check_in + timedelta(days=2)
            nights = (check_out - check_in).days
            total = Decimal(room.base_price) * nights
            advance = (total * Decimal('0.30')).quantize(Decimal('0.01'))
            status = statuses[idx % len(statuses)]
            booking, _ = HotelBooking.objects.update_or_create(
                hotel=hotel,
                room=room,
                user=guest,
                check_in=check_in,
                defaults={
                    'guest_name': guest.name,
                    'guest_phone': guest.phone,
                    'guest_email': guest.email,
                    'check_out': check_out,
                    'guests': min(room.capacity, 2),
                    'status': status,
                    'payment_status': (
                        HotelPayStatus.PAID
                        if status != HotelBookingStatus.PENDING
                        else HotelPayStatus.PENDING
                    ),
                    'total_amount': total,
                    'advance_amount': advance,
                    'remaining_amount': total - advance,
                    'payment_method': HotelPayMethod.BKASH,
                    'transaction_id': f'BKS-HTL-{idx + 1:03d}{guest.phone[-4:]}',
                    'special_requests': 'Non-smoking room, early check-in if possible.',
                    'fee_breakdown': {
                        'nights': nights,
                        'base': str(room.base_price),
                        'vatPercent': 15,
                    },
                },
            )
            if status == HotelBookingStatus.COMPLETED:
                HotelReview.objects.update_or_create(
                    hotel=hotel,
                    user=guest,
                    defaults={
                        'booking': booking,
                        'rating': 4 + (idx % 2),
                        'comment': (
                            f'Stay at {hotel.name} was comfortable. Staff spoke Bangla and English, '
                            'and the location matched the listing.'
                        ),
                    },
                )
                hotel.refresh_rating_cache()
        self.stdout.write('  hotel bookings and reviews')

    def _verifications(self, renters, owners):
        admin = User.objects.filter(role=Role.ADMIN).first()
        samples = (owners[:2] + renters[:3])
        for user in samples:
            VerificationDocument.objects.update_or_create(
                user=user,
                verification_type=VerificationDocument.VerificationType.NID,
                defaults={
                    'document_number': f'19{user.phone[-10:]}',
                    'file_name': 'nid-scan.jpg',
                    'status': VerificationDocument.Status.VERIFIED,
                    'reviewed_at': timezone.now(),
                    'reviewed_by': admin,
                },
            )
        pending = User.objects.filter(phone='+8801710000008').first()
        if pending:
            VerificationDocument.objects.update_or_create(
                user=pending,
                verification_type=VerificationDocument.VerificationType.NID,
                defaults={
                    'document_number': '1990123456789',
                    'file_name': 'nid-pending.jpg',
                    'status': VerificationDocument.Status.PENDING,
                },
            )
        self.stdout.write('  NID verifications')

    def _notifications(self, renters):
        for renter in renters[:5]:
            Notification.objects.get_or_create(
                user=renter,
                title='August rent reminder',
                defaults={
                    'message': 'Your rent for this month is due by the 10th. Pay via bKash or Nagad.',
                    'type': NotificationType.BILL,
                    'read': False,
                    'link': '/payments',
                },
            )
        self.stdout.write('  renter notifications')

    def _boosts(self, properties, now):
        featured = [p for p in properties if p.featured][:3]
        for prop in featured:
            FeaturedBoost.objects.update_or_create(
                owner=prop.owner,
                property=prop,
                boost_option_id='boost-30',
                defaults={
                    'duration_days': 30,
                    'price': Decimal('899'),
                    'paid_at': now,
                    'featured_until': (now + timedelta(days=30)).date(),
                },
            )
            sub = get_or_create_owner_subscription(prop.owner)
            if sub.plan.tier == PlanTier.FREE:
                pass
            sub.active_featured_listings = FeaturedBoost.objects.filter(
                owner=prop.owner,
            ).count()
            sub.save(update_fields=['active_featured_listings', 'updated_at'])
        self.stdout.write('  featured boosts')

    def _schedules(self, renters):
        renter = User.objects.filter(phone='+8801710000001').first()
        if not renter:
            return
        bill = Bill.objects.filter(tenant=renter, is_deleted=False).order_by('-year').first()
        PaymentSchedule.objects.update_or_create(
            user=renter,
            name='Monthly mess + rent',
            defaults={
                'description': 'Auto reminder for Green Valley bills',
                'bill': bill,
                'recurring': True,
                'frequency': ScheduleFrequency.MONTHLY,
                'start_date': date(2026, 1, 5),
                'amount': Decimal('12500'),
                'payment_method': PaymentMethod.BKASH,
                'reminder_enabled': True,
                'reminder_days': [3, 1],
                'is_active': True,
            },
        )
        if bill:
            ScheduledPayment.objects.update_or_create(
                user=renter,
                bill=bill,
                scheduled_date=date(2026, 9, 5),
                defaults={
                    'bill_name': f'{bill.month} {bill.year} — {bill.property_name}',
                    'amount': bill.amount,
                    'scheduled_time': '10:00',
                    'payment_method': PaymentMethod.BKASH,
                    'account_number': renter.phone[-11:],
                    'status': ScheduledPaymentStatus.SCHEDULED,
                    'reminder_enabled': True,
                    'reminder_days': [3, 1],
                },
            )
        self.stdout.write('  payment schedules')
