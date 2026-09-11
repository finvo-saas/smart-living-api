"""
Production-level complete seed: fill every major model with parent→child
relations across mess, apartment, and hotel verticals.

Idempotent. Run after the base domain seeds (via seed_all) or alone after
users/portfolio/mess/hotels already exist.

Demo PIN for seeded users: 1234
Demo OTP (DEBUG + console SMS): 123456
"""

from __future__ import annotations

import secrets
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User, UserProfile, VerificationDocument
from accounts.services.pin import set_user_pin
from billing.models import (
    Bill,
    BillGenerationRule,
    BillItem,
    BillItemType,
    BillStatus,
    BillTemplate,
    BillTemplateItem,
    CalculationType,
    MeterReading,
    MeterType,
    PropertyKind,
)
from billing.services.generation import MONTH_NAMES, default_due_date
from bookings.models import BookingMode, BookingStatus, PropertyBooking
from core.scope import ScopeType
from core.seed_catalog import APT_OWNER_PHONES, ensure_user, resolve_owner
from discovery.models import (
    Favorite,
    HeartbeatPing,
    HeartbeatStatus,
    HeartbeatTargetType,
    SavedSearch,
)
from documents.models import (
    AgreementStatus,
    AgreementType,
    Checklist,
    ChecklistStatus,
    ChecklistType,
    RentalAgreement,
)
from hotels.models import (
    Hotel,
    HotelBooking,
    HotelBookingStatus,
    HotelReview,
    PaymentMethod as HotelPaymentMethod,
    PaymentStatus as HotelPaymentStatus,
    Room,
    RoomPrice,
)
from listings.models import Property
from mess.models import (
    DepositStatus,
    MealOffRequest,
    MealOffStatus,
    MealPreference,
    MemberDeposit,
    MemberMealLog,
    MemberMonthBill,
    Mess,
    MessMonthClose,
    MessStudent,
    MonthCloseStatus,
    OwnerSMSAccount,
    RuleAcceptance,
    Seat,
    SMSCreditLedger,
    SMSCreditPackage,
    SMSCreditPurchase,
)
from messaging.models import Chat, ChatMessage, MessageType, Notification, NotificationType
from ops.models import Notice, NoticeAck, NoticeCategory, NoticePriority
from payments.models import (
    CollectionMode,
    OwnerCollectionSettings,
    OwnerGatewayCredential,
    PaymentClaim,
    PaymentClaimStatus,
    PaymentGateway,
    PaymentMethod,
    PaymentSchedule,
    PaymentTransaction,
    PaymentTransactionStatus,
    ScheduleFrequency,
    ScheduledPayment,
    ScheduledPaymentStatus,
)
from portfolio.models import Building, Flat, FlatStatus, Floor, Tenancy, TenancyStatus
from portfolio.services.seed_buildings import ensure_building
from support.models import Complaint, ComplaintCategory, ComplaintMessage, ComplaintStatus


DEMO_PIN = '1234'

APT_OWNER = '+8801712345680'  # Karim — apartment (catalog)
APT_OWNER_ALT = '+8801917161305'  # Karim — apartment (product remapped)
MESS_OWNER = '+8801712345678'  # Abdul — mess
MESS_OWNER_ALT = '+8801917161352'
HOTEL_OWNER = '+8801512345678'  # Tanvir — hotel
RENTERS = [
    '+8801710000001',  # Rahim
    '+8801710000002',  # Sadia
    '+8801710000003',  # Imran
    '+8801710000004',
    '+8801710000005',
]


def _user(phone: str) -> User | None:
    return User.objects.filter(phone=phone).first()


def _ensure_pin(user: User) -> None:
    if user.pin_set_at:
        return
    set_user_pin(user, DEMO_PIN)


def _month_label(d: date) -> str:
    return MONTH_NAMES[d.month]


def _shift_month(d: date, months_ago: int) -> date:
    y, m = d.year, d.month - months_ago
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


class Command(BaseCommand):
    help = (
        'Complete relational seed for mess / apartment / hotel — every major '
        'model with parent→child→tenant links for production-level QA.'
    )

    def handle(self, *args, **options):
        with transaction.atomic():
            self._pins_and_focus()
            self._apartment_tree()
            self._mess_tree()
            self._hotel_tree()
            self._shared_discovery()
        self.stdout.write(self.style.SUCCESS('seed_complete finished.'))
        self._print_logins()

    def _pins_and_focus(self):
        # Ensure canonical demo identities exist even if seed_users was skipped
        for phone in APT_OWNER_PHONES:
            ensure_user(
                phone=phone,
                name='Karim Hossain',
                role=Role.OWNER,
                email='karim.hossain@smartbasa.com',
            )
        ensure_user(
            phone=MESS_OWNER,
            name='Abdul Karim',
            role=Role.OWNER,
            email='abdul.karim@smartbasa.com',
        )
        ensure_user(
            phone=MESS_OWNER_ALT,
            name='Abdul Karim',
            role=Role.OWNER,
            email='abdul.karim.alt@smartbasa.com',
        )
        ensure_user(
            phone=HOTEL_OWNER,
            name='Tanvir Hasan',
            role=Role.OWNER,
            email='tanvir.hasan@smartbasa.com',
        )
        renter_names = [
            'Rahim Uddin',
            'Sadia Akter',
            'Imran Hossain',
            'Nabila Rahman',
            'Karim Mia',
        ]
        for phone, name in zip(RENTERS, renter_names):
            ensure_user(phone=phone, name=name, role=Role.RENTER)

        phones = (
            list(APT_OWNER_PHONES)
            + [MESS_OWNER, MESS_OWNER_ALT, HOTEL_OWNER]
            + RENTERS
            + ['+8801711111111', '+8801712345679', '+8801912345678', '+8801612345678']
        )
        for phone in phones:
            u = _user(phone)
            if not u:
                continue
            _ensure_pin(u)
            UserProfile.objects.get_or_create(user=u)
        self.stdout.write('  pins + profiles OK')

    # -------------------------------------------------------------- apartment
    def _apartment_tree(self):
        owner = resolve_owner(*APT_OWNER_PHONES)
        if not owner:
            self.stdout.write(self.style.WARNING('  skip apartment: no owner'))
            return

        building, _ = ensure_building(
            owner=owner,
            name='Green Valley',
            defaults={
                'address': 'House 45, Road 7, Block C, Mirpur-10',
                'city': 'Dhaka',
                'total_floors': 3,
                'total_flats': 6,
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

        flat_specs = [
            ('1A', 1, 12000, FlatStatus.OCCUPIED, RENTERS[0]),
            ('1B', 1, 12500, FlatStatus.OCCUPIED, RENTERS[1]),
            ('2A', 2, 15000, FlatStatus.AVAILABLE, None),
            ('2B', 2, 15000, FlatStatus.OCCUPIED, RENTERS[2]),
            ('3A', 3, 18000, FlatStatus.AVAILABLE, None),
            ('3B', 3, 18000, FlatStatus.MAINTENANCE, None),
        ]
        flats: dict[str, Flat] = {}
        for number, fnum, rent, status, renter_phone in flat_specs:
            flat, _ = Flat.objects.update_or_create(
                building=building,
                flat_number=number,
                defaults={
                    'floor': floors[fnum],
                    'floor_number': fnum,
                    'rent': Decimal(rent),
                    'status': status,
                    'bedrooms': 2 if fnum < 3 else 3,
                    'bathrooms': 1,
                    'area': 850 + fnum * 50,
                },
            )
            flats[number] = flat
            if renter_phone:
                renter = _user(renter_phone)
                if renter:
                    Tenancy.objects.filter(
                        flat=flat,
                        status=TenancyStatus.ACTIVE,
                    ).exclude(tenant=renter).update(
                        status=TenancyStatus.ENDED,
                        end_date=date.today(),
                    )
                    Tenancy.objects.update_or_create(
                        flat=flat,
                        tenant=renter,
                        status=TenancyStatus.ACTIVE,
                        defaults={
                            'start_date': date.today() - timedelta(days=90),
                            'deposit': Decimal(rent),
                            'tenant_name': renter.name or '',
                            'tenant_phone': renter.phone,
                            'tenant_whatsapp': renter.whatsapp_number or renter.phone,
                            'tenant_email': renter.email or '',
                            'notes': 'Seed active tenancy',
                        },
                    )
                    flat.status = FlatStatus.OCCUPIED
                    flat.save(update_fields=['status', 'updated_at'])

        if hasattr(building, 'refresh_counts'):
            building.refresh_counts()
        else:
            building.total_floors = 3
            building.total_flats = 6
            building.save(update_fields=['total_floors', 'total_flats', 'updated_at'])

        listing = Property.objects.filter(
            owner=owner,
            type='apartment',
            published=True,
        ).first() or Property.objects.filter(owner=owner, type='apartment').first()
        if listing and flats.get('2A') and not flats['2A'].listing_id:
            flats['2A'].listing = listing
            flats['2A'].save(update_fields=['listing', 'updated_at'])

        template, _ = BillTemplate.objects.update_or_create(
            owner=owner,
            name='Green Valley Standard',
            property_id=building.id,
            defaults={
                'description': 'Monthly rent + service',
                'property_type': PropertyKind.APARTMENT,
                'is_active': True,
            },
        )
        BillTemplateItem.objects.filter(template=template).delete()
        BillTemplateItem.objects.create(
            template=template,
            description='Monthly rent',
            type=BillItemType.RENT,
            calculation_type=CalculationType.FIXED,
            fixed_amount=Decimal('12000'),
        )
        BillTemplateItem.objects.create(
            template=template,
            description='Service charge',
            type=BillItemType.OTHER,
            calculation_type=CalculationType.FIXED,
            fixed_amount=Decimal('1500'),
        )

        next_run = (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)
        BillGenerationRule.objects.update_or_create(
            owner=owner,
            name='Green Valley monthly',
            defaults={
                'description': 'Auto rent on the 1st',
                'property_id': building.id,
                'property_type': PropertyKind.APARTMENT,
                'template': template,
                'schedule': {'dayOfMonth': 1},
                'is_active': True,
                'next_run': next_run,
            },
        )

        today = date.today()
        bill_specs = [
            ('1A', RENTERS[0], BillStatus.UNPAID, 0),
            ('1A', RENTERS[0], BillStatus.PAID, 1),
            ('1B', RENTERS[1], BillStatus.OVERDUE, 1),
            ('2B', RENTERS[2], BillStatus.UNPAID, 0),
        ]
        for flat_number, renter_phone, status, months_ago in bill_specs:
            flat = flats[flat_number]
            renter = _user(renter_phone)
            if not renter:
                continue
            ref = _shift_month(today, months_ago)
            month = _month_label(ref)
            year = ref.year
            amount = flat.rent + Decimal('1500')
            meter, _ = MeterReading.objects.update_or_create(
                owner=owner,
                property_id=building.id,
                flat=flat,
                month=month,
                year=year,
                defaults={
                    'property_type': PropertyKind.APARTMENT,
                    'electricity': 1285.0,
                    'gas': 48.0,
                    'water': 32.0,
                    'previous_electricity': 1200.0,
                    'previous_gas': 42.0,
                    'previous_water': 28.0,
                    'electricity_consumption': 85.0,
                    'gas_consumption': 6.0,
                    'water_consumption': 4.0,
                    'submitted_by': owner,
                },
            )
            bill, created = Bill.objects.update_or_create(
                owner=owner,
                property_id=building.id,
                flat=flat,
                month=month,
                year=year,
                defaults={
                    'tenant': renter,
                    'tenant_name': renter.name or '',
                    'tenant_id_snapshot': str(renter.id),
                    'property_type': PropertyKind.APARTMENT,
                    'property_name': building.name,
                    'flat_number': flat.flat_number,
                    'amount': amount,
                    'amount_paid': amount if status == BillStatus.PAID else Decimal('0'),
                    'due_date': default_due_date(year, month),
                    'paid_date': (today - timedelta(days=20)) if status == BillStatus.PAID else None,
                    'status': status,
                    'template': template,
                    'meter_reading': meter,
                },
            )
            if created or not bill.items.exists():
                BillItem.objects.filter(bill=bill).delete()
                BillItem.objects.create(
                    bill=bill,
                    description='Rent',
                    amount=flat.rent,
                    type=BillItemType.RENT,
                    calculation_type=CalculationType.FIXED,
                )
                BillItem.objects.create(
                    bill=bill,
                    description='Service',
                    amount=Decimal('1500'),
                    type=BillItemType.OTHER,
                    calculation_type=CalculationType.FIXED,
                )

        OwnerCollectionSettings.objects.update_or_create(
            owner=owner,
            defaults={
                'collection_mode': CollectionMode.OWNER_GATEWAY,
                'bkash_number': '01712345680',
                'nagad_number': '01712345680',
                'payment_note': 'Send to bKash Personal — seed',
            },
        )
        OwnerGatewayCredential.objects.update_or_create(
            owner=owner,
            gateway=PaymentGateway.BKASH,
            defaults={
                'display_name': 'Karim bKash merchant',
                'merchant_number': '01712345680',
                'credentials': {'sandbox': True, 'seed': True},
                'is_active': True,
                'is_sandbox': True,
            },
        )

        unpaid = (
            Bill.objects.filter(
                owner=owner,
                status=BillStatus.UNPAID,
                property_type=PropertyKind.APARTMENT,
                tenant__isnull=False,
            )
            .order_by('-created_at')
            .first()
        )
        if unpaid and unpaid.tenant_id:
            txn_id = f'SEED-APT-{unpaid.id.hex[:10]}'
            PaymentTransaction.objects.update_or_create(
                transaction_id=txn_id,
                defaults={
                    'user': unpaid.tenant,
                    'bill': unpaid,
                    'bill_name': f'{unpaid.property_name} {unpaid.month} {unpaid.year}',
                    'property_name': unpaid.property_name,
                    'tenant_name': unpaid.tenant_name,
                    'amount': unpaid.amount,
                    'payment_method': PaymentMethod.BKASH,
                    'account_number': '01712345680',
                    'status': PaymentTransactionStatus.PENDING,
                },
            )
            ScheduledPayment.objects.update_or_create(
                user=unpaid.tenant,
                bill=unpaid,
                defaults={
                    'bill_name': f'{unpaid.property_name} rent',
                    'amount': unpaid.amount,
                    'scheduled_date': today + timedelta(days=3),
                    'status': ScheduledPaymentStatus.SCHEDULED,
                    'payment_method': PaymentMethod.BKASH,
                    'account_number': '01710000001',
                },
            )
            PaymentSchedule.objects.update_or_create(
                user=unpaid.tenant,
                bill=unpaid,
                name='Green Valley auto-pay',
                defaults={
                    'description': 'Monthly rent schedule — seed',
                    'amount': unpaid.amount,
                    'frequency': ScheduleFrequency.MONTHLY,
                    'start_date': today,
                    'payment_method': PaymentMethod.BKASH,
                    'recurring': True,
                    'is_active': True,
                },
            )
            PaymentClaim.objects.update_or_create(
                bill=unpaid,
                claimed_by=unpaid.tenant,
                defaults={
                    'amount': unpaid.amount,
                    'payment_method': PaymentMethod.CASH,
                    'status': PaymentClaimStatus.PENDING,
                    'note': 'Seed cash claim — paid to caretaker',
                    'transaction_id': f'CASH-{unpaid.id.hex[:8]}',
                },
            )

        notice, _ = Notice.objects.update_or_create(
            scope_type=ScopeType.BUILDING,
            scope_id=building.id,
            title='Water supply maintenance Friday',
            defaults={
                'scope_name': building.name,
                'content': 'Tank cleaning 10am–2pm. Please store water.',
                'date': today,
                'priority': NoticePriority.HIGH,
                'category': NoticeCategory.MAINTENANCE,
                'created_by': owner,
                'is_deleted': False,
                'target_ids': [],
            },
        )
        for phone in (RENTERS[0], RENTERS[1]):
            r = _user(phone)
            if r:
                NoticeAck.objects.update_or_create(
                    notice=notice,
                    user=r,
                    defaults={
                        'acknowledged_at': timezone.now(),
                        'user_name': r.name or '',
                    },
                )

        renter = _user(RENTERS[0])
        flat = flats.get('1A')
        if renter and flat:
            complaint, _ = Complaint.objects.update_or_create(
                user=renter,
                title='Kitchen tap leaking',
                defaults={
                    'user_name': renter.name or '',
                    'description': 'Cold water tap drips continuously since yesterday.',
                    'status': ComplaintStatus.IN_PROGRESS,
                    'category': ComplaintCategory.MAINTENANCE,
                    'scope_type': ScopeType.BUILDING,
                    'scope_id': building.id,
                    'scope_name': building.name,
                    'target_id': flat.id,
                    'target_label': flat.flat_number,
                    'building': building,
                    'flat': flat,
                    'response': 'Plumber scheduled for tomorrow.',
                    'is_deleted': False,
                },
            )
            if not complaint.messages.exists():
                ComplaintMessage.objects.create(
                    complaint=complaint,
                    author=renter,
                    author_name=renter.name or '',
                    body=complaint.description,
                    is_staff_reply=False,
                )
                ComplaintMessage.objects.create(
                    complaint=complaint,
                    author=owner,
                    author_name=owner.name or '',
                    body='Plumber scheduled for tomorrow morning.',
                    is_staff_reply=True,
                )

            RentalAgreement.objects.update_or_create(
                user=renter,
                property_id=building.id,
                flat_id=flat.id,
                defaults={
                    'scope_type': ScopeType.BUILDING,
                    'scope_id': building.id,
                    'property_name': building.name,
                    'flat_number': flat.flat_number,
                    'agreement_type': AgreementType.RENTAL,
                    'start_date': today - timedelta(days=90),
                    'end_date': today + timedelta(days=275),
                    'monthly_rent': flat.rent,
                    'security_deposit': flat.rent,
                    'expiry_date': today + timedelta(days=275),
                    'renewal_reminder_days': [30, 14, 7],
                    'status': AgreementStatus.ACTIVE,
                    'uploaded_by': str(owner.id),
                    'document_name': 'green-valley-1a.pdf',
                },
            )
            Checklist.objects.update_or_create(
                user=renter,
                property_id=building.id,
                flat_id=flat.id,
                type=ChecklistType.MOVE_IN,
                defaults={
                    'scope_type': ScopeType.BUILDING,
                    'scope_id': building.id,
                    'property_name': building.name,
                    'flat_number': flat.flat_number,
                    'items': [
                        {'name': 'Keys', 'ok': True},
                        {'name': 'Fridge', 'ok': True},
                        {'name': 'AC', 'ok': False, 'note': 'Needs service'},
                    ],
                    'status': ChecklistStatus.COMPLETED,
                    'completed_at': timezone.now() - timedelta(days=85),
                    'completed_by': renter.name or '',
                    'security_deposit_amount': flat.rent,
                },
            )

            p1, p2 = (owner, renter) if str(owner.id) < str(renter.id) else (renter, owner)
            chat, _ = Chat.objects.get_or_create(
                participant1=p1,
                participant2=p2,
                defaults={
                    'participant1_name': p1.name or p1.phone,
                    'participant2_name': p2.name or p2.phone,
                    'property_id': building.id,
                    'property_name': building.name,
                    'last_message': 'Assalamualaikum, rent bill received.',
                    'last_message_time': timezone.now(),
                },
            )
            if not chat.messages.exists():
                ChatMessage.objects.create(
                    chat=chat,
                    sender=renter,
                    receiver=owner,
                    type=MessageType.TEXT,
                    content='Assalamualaikum, rent bill received.',
                )
                chat.last_message = 'Assalamualaikum, rent bill received.'
                chat.last_message_time = timezone.now()
                chat.save(update_fields=['last_message', 'last_message_time', 'updated_at'])

            Notification.objects.get_or_create(
                user=renter,
                title='Rent due reminder',
                defaults={
                    'message': 'Your rent for this month is unpaid.',
                    'type': NotificationType.BILL,
                    'read': False,
                    'link': '/bills',
                },
            )
            VerificationDocument.objects.update_or_create(
                user=renter,
                verification_type=VerificationDocument.VerificationType.NID,
                defaults={
                    'document_number': '1234567890123',
                    'file_name': 'nid-rahim.pdf',
                    'status': VerificationDocument.Status.VERIFIED,
                    'reviewed_at': timezone.now() - timedelta(days=60),
                    'reviewed_by': owner,
                },
            )

        if listing and flats.get('2A'):
            seeker = _user(RENTERS[3]) or _user(RENTERS[0])
            if seeker:
                PropertyBooking.objects.get_or_create(
                    property=listing,
                    renter=seeker,
                    status=BookingStatus.PENDING,
                    defaults={
                        'owner': owner,
                        'property_name': listing.name,
                        'property_type': listing.type,
                        'property_address': listing.address or '',
                        'property_image': (listing.images or [''])[0] if listing.images else '',
                        'renter_name': seeker.name or '',
                        'renter_phone': seeker.phone,
                        'renter_email': seeker.email or '',
                        'owner_name': owner.name or '',
                        'owner_phone': owner.phone,
                        'booking_mode': BookingMode.REQUEST,
                        'move_in_date': today + timedelta(days=14),
                        'duration': 12,
                        'rent': listing.rent or Decimal('15000'),
                        'deposit': listing.rent or Decimal('15000'),
                        'total_amount': (listing.rent or Decimal('15000')) * 2,
                        'message': 'Interested in flat 2A — seed request',
                    },
                )

        self.stdout.write(self.style.SUCCESS(f'  apartment tree: {building.name}'))

    # ------------------------------------------------------------------- mess
    def _mess_tree(self):
        owner = _user(MESS_OWNER_ALT) or _user(MESS_OWNER)
        if not owner:
            self.stdout.write(self.style.WARNING('  skip mess: no owner'))
            return

        mess = (
            Mess.objects.filter(owner=owner, is_deleted=False).order_by('created_at').first()
            or Mess.objects.filter(name='Green Valley Mess', is_deleted=False).first()
            or Mess.objects.filter(is_deleted=False).order_by('created_at').first()
        )
        if not mess:
            self.stdout.write(self.style.WARNING('  skip mess: no Mess row'))
            return

        if mess.owner_id != owner.id:
            mess.owner = owner
            mess.owner_phone = owner.phone
            mess.save(update_fields=['owner', 'owner_phone', 'updated_at'])

        students = list(
            MessStudent.objects.filter(mess=mess, is_deleted=False, is_active=True)[:5],
        )
        today = date.today()

        notice, _ = Notice.objects.update_or_create(
            scope_type=ScopeType.MESS,
            scope_id=mess.id,
            title='Meal off deadline tonight',
            defaults={
                'scope_name': mess.name,
                'content': 'Mark meal-off before 9pm for tomorrow.',
                'date': today,
                'priority': NoticePriority.MEDIUM,
                'category': NoticeCategory.ANNOUNCEMENT,
                'created_by': owner,
                'is_deleted': False,
                'target_ids': [],
            },
        )
        for st in students[:3]:
            if st.user_id:
                NoticeAck.objects.update_or_create(
                    notice=notice,
                    user_id=st.user_id,
                    defaults={
                        'acknowledged_at': timezone.now(),
                        'user_name': st.name,
                    },
                )

        for st in students[:3]:
            MemberDeposit.objects.update_or_create(
                mess=mess,
                student=st,
                date=today - timedelta(days=60),
                defaults={
                    'amount': Decimal('3000'),
                    'status': DepositStatus.CONFIRMED,
                    'note': 'Seed security deposit',
                    'payment_method': 'bKash',
                    'transaction_id': f'DEP-{st.id.hex[:8]}',
                    'created_by': owner,
                    'confirmed_by': owner,
                    'is_deleted': False,
                },
            )
            if st.user_id:
                MealPreference.objects.update_or_create(
                    user_id=st.user_id,
                    mess=mess,
                    defaults={
                        'preferences': ['no_beef_friday', 'extra_rice_ok'],
                    },
                )
            rule = mess.rules.filter(is_deleted=False).first()
            if rule:
                RuleAcceptance.objects.update_or_create(
                    rule=rule,
                    student=st,
                    defaults={
                        'student_name': st.name,
                        'accepted_at': timezone.now() - timedelta(days=30),
                        'accepted_by_id': st.user_id,
                    },
                )

            for day_offset in range(3):
                d = today - timedelta(days=day_offset)
                MemberMealLog.objects.update_or_create(
                    mess=mess,
                    student=st,
                    date=d,
                    defaults={
                        'breakfast': Decimal('1'),
                        'lunch': Decimal('1'),
                        'dinner': Decimal('1'),
                        'guest_lunch': 0,
                        'marked_by': owner,
                        'notes': 'Seed meal log',
                    },
                )

        if students:
            MealOffRequest.objects.update_or_create(
                mess=mess,
                student=students[0],
                start_date=today + timedelta(days=1),
                end_date=today + timedelta(days=1),
                defaults={
                    'meals': {'breakfast': False, 'lunch': True, 'dinner': True},
                    'status': MealOffStatus.APPROVED,
                    'reason': 'Going home — seed',
                    'reviewed_by': owner,
                    'reviewed_at': timezone.now(),
                },
            )

        close, _ = MessMonthClose.objects.update_or_create(
            mess=mess,
            year=today.year,
            month=today.month,
            defaults={
                'status': MonthCloseStatus.CLOSED,
                'bazaar_total': Decimal('45000'),
                'fixed_total': Decimal('12000'),
                'total_meals': Decimal('600'),
                'meal_rate': Decimal('75'),
                'guest_meal_total': Decimal('1500'),
                'closed_at': timezone.now(),
                'closed_by': owner,
                'snapshot': {'seed': True},
            },
        )
        for st in students[:4]:
            MemberMonthBill.objects.update_or_create(
                month_close=close,
                student=st,
                defaults={
                    'student_name': st.name,
                    'meal_count': Decimal('60'),
                    'meal_cost': Decimal('4500'),
                    'guest_meals': 2,
                    'guest_cost': Decimal('200'),
                    'fixed_share': Decimal('800'),
                    'deposits': Decimal('0'),
                    'total': Decimal('5500'),
                    'due': Decimal('5500'),
                    'credit': Decimal('0'),
                },
            )

        if students and students[0].user_id:
            st = students[0]
            month = _month_label(today)
            seat_number = ''
            if st.seat_id:
                try:
                    seat_number = st.seat.seat_number
                except Seat.DoesNotExist:
                    seat_number = ''
            Bill.objects.update_or_create(
                owner=owner,
                property_id=mess.id,
                month=month,
                year=today.year,
                tenant_id=st.user_id,
                defaults={
                    'property_type': PropertyKind.MESS,
                    'property_name': mess.name,
                    'tenant_name': st.name,
                    'tenant_id_snapshot': str(st.user_id),
                    'seat_number': seat_number,
                    'status': BillStatus.UNPAID,
                    'due_date': default_due_date(today.year, month),
                    'amount': st.monthly_fee or Decimal('5500'),
                    'flat': None,
                    'flat_number': '',
                },
            )

        pkg, _ = SMSCreditPackage.objects.update_or_create(
            package_key='sms-100-seed',
            defaults={
                'label': '100 SMS (seed)',
                'credits': 100,
                'price_bdt': Decimal('250'),
                'description': 'Demo SMS pack',
                'is_active': True,
                'sort_order': 10,
            },
        )
        acct, _ = OwnerSMSAccount.objects.update_or_create(
            owner=owner,
            defaults={
                'balance': 120,
                'lifetime_purchased': 200,
                'lifetime_granted': 50,
                'lifetime_used': 130,
            },
        )
        purchase, _ = SMSCreditPurchase.objects.update_or_create(
            owner=owner,
            package_id=pkg.package_key,
            defaults={
                'credits': pkg.credits,
                'amount_bdt': pkg.price_bdt,
                'status': SMSCreditPurchase.Status.PAID,
                'paid_at': timezone.now() - timedelta(days=10),
            },
        )
        ledger, _ = SMSCreditLedger.objects.update_or_create(
            account=acct,
            entry_type=SMSCreditLedger.EntryType.PURCHASE,
            note='Seed top-up',
            defaults={
                'credits': 100,
                'balance_after': acct.balance,
                'mess': mess,
            },
        )
        if purchase.ledger_entry_id != ledger.id:
            purchase.ledger_entry = ledger
            purchase.save(update_fields=['ledger_entry', 'updated_at'])

        if students and students[0].user_id:
            st = students[0]
            Complaint.objects.update_or_create(
                user_id=st.user_id,
                title='Wifi down in seat wing',
                defaults={
                    'user_name': st.name,
                    'description': 'No internet since morning in seats 1–8.',
                    'status': ComplaintStatus.OPEN,
                    'category': ComplaintCategory.MAINTENANCE,
                    'scope_type': ScopeType.MESS,
                    'scope_id': mess.id,
                    'scope_name': mess.name,
                    'is_deleted': False,
                },
            )

        self.stdout.write(self.style.SUCCESS(f'  mess tree: {mess.name}'))

    # ------------------------------------------------------------------ hotel
    def _hotel_tree(self):
        owner = _user(HOTEL_OWNER)
        if not owner:
            self.stdout.write(self.style.WARNING('  skip hotel: no owner'))
            return

        hotel = Hotel.objects.filter(owner=owner, is_deleted=False).first()
        if not hotel:
            hotel = Hotel.objects.filter(
                name='Grand Plaza Hotel Dhaka',
                is_deleted=False,
            ).first()
            if hotel:
                hotel.owner = owner
                hotel.owner_phone = owner.phone
                hotel.owner_name = owner.name or ''
                hotel.save(update_fields=['owner', 'owner_phone', 'owner_name', 'updated_at'])
        if not hotel:
            hotel = Hotel.objects.filter(is_deleted=False).first()
            if hotel:
                hotel.owner = owner
                hotel.owner_phone = owner.phone
                hotel.owner_name = owner.name or ''
                hotel.save(update_fields=['owner', 'owner_phone', 'owner_name', 'updated_at'])
        if not hotel:
            self.stdout.write(self.style.WARNING('  skip hotel: no Hotel row'))
            return

        rooms = list(Room.objects.filter(hotel=hotel)[:5])
        today = date.today()
        for room in rooms[:2]:
            for offset in range(0, 7):
                d = today + timedelta(days=offset)
                price = room.base_price * (Decimal('1.2') if d.weekday() >= 5 else Decimal('1'))
                RoomPrice.objects.update_or_create(
                    room=room,
                    date=d,
                    defaults={
                        'price': price.quantize(Decimal('0.01')),
                        'is_weekend': d.weekday() >= 5,
                    },
                )

        guest = _user(RENTERS[1]) or _user(RENTERS[0])
        booking = None
        if guest and rooms:
            room = rooms[0]
            check_in = today + timedelta(days=2)
            check_out = today + timedelta(days=4)
            nights = (check_out - check_in).days
            total = (room.base_price * nights).quantize(Decimal('0.01'))
            booking, _ = HotelBooking.objects.update_or_create(
                hotel=hotel,
                room=room,
                user=guest,
                check_in=check_in,
                defaults={
                    'guest_name': guest.name or 'Guest',
                    'guest_phone': guest.phone,
                    'guest_email': guest.email or '',
                    'check_out': check_out,
                    'guests': 2,
                    'total_amount': total,
                    'advance_amount': room.base_price,
                    'remaining_amount': total - room.base_price,
                    'status': HotelBookingStatus.CONFIRMED,
                    'payment_status': HotelPaymentStatus.PARTIAL,
                    'payment_method': HotelPaymentMethod.BKASH,
                    'transaction_id': f'HB-{hotel.id.hex[:8]}',
                    'special_requests': 'High floor if possible — seed',
                    'is_deleted': False,
                },
            )
            HotelReview.objects.update_or_create(
                hotel=hotel,
                user=guest,
                defaults={
                    'booking': booking,
                    'user_name': guest.name or '',
                    'rating': 5,
                    'comment': 'Clean rooms, great location — seed review',
                    'owner_response': 'Thank you for staying with us!',
                    'owner_response_date': timezone.now(),
                },
            )

        Notice.objects.update_or_create(
            scope_type=ScopeType.HOTEL,
            scope_id=hotel.id,
            title='Checkout by 12:00',
            defaults={
                'scope_name': hotel.name,
                'content': 'Late checkout available on request (+BDT 500/hour).',
                'date': today,
                'priority': NoticePriority.LOW,
                'category': NoticeCategory.RULE,
                'created_by': owner,
                'is_deleted': False,
                'target_ids': [],
            },
        )

        if guest:
            Complaint.objects.update_or_create(
                user=guest,
                title='AC not cooling in room',
                defaults={
                    'user_name': guest.name or '',
                    'description': 'Room AC blows warm air.',
                    'status': ComplaintStatus.OPEN,
                    'category': ComplaintCategory.MAINTENANCE,
                    'scope_type': ScopeType.HOTEL,
                    'scope_id': hotel.id,
                    'scope_name': hotel.name,
                    'target_id': rooms[0].id if rooms else None,
                    'target_label': rooms[0].room_number if rooms else '',
                    'is_deleted': False,
                },
            )

        self.stdout.write(self.style.SUCCESS(f'  hotel tree: {hotel.name}'))

    # ------------------------------------------------------------- discovery
    def _shared_discovery(self):
        renter = _user(RENTERS[0])
        if not renter:
            return
        prop = Property.objects.filter(published=True).first() or Property.objects.first()
        if prop:
            Favorite.objects.get_or_create(user=renter, property=prop)
            SavedSearch.objects.update_or_create(
                user=renter,
                name='Mirpur under 20k',
                defaults={
                    'filters': {'city': 'Dhaka', 'maxRent': 20000, 'type': 'apartment'},
                    'is_active': True,
                    'match_count': 3,
                },
            )
            token = secrets.token_urlsafe(24)[:48]
            existing = HeartbeatPing.objects.filter(
                target_type=HeartbeatTargetType.LISTING,
                target_id=prop.id,
                owner=prop.owner,
            ).first()
            if not existing:
                HeartbeatPing.objects.create(
                    token=token,
                    owner=prop.owner,
                    target_type=HeartbeatTargetType.LISTING,
                    target_id=prop.id,
                    target_name=prop.name,
                    target_city=getattr(prop, 'city', '') or 'Dhaka',
                    status=HeartbeatStatus.CONFIRMED,
                    channel='sms',
                    sent_at=timezone.now() - timedelta(days=2),
                    responded_at=timezone.now() - timedelta(days=1),
                    expires_at=timezone.now() + timedelta(days=5),
                    sms_body='Seed heartbeat: still available?',
                )
        self.stdout.write('  discovery extras OK')

    def _print_logins(self):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Demo logins'))
        self.stdout.write(f'  PIN (all seeded users): {DEMO_PIN}')
        self.stdout.write('  OTP (DEBUG console):     123456')
        self.stdout.write(f'  Apartment owner: {APT_OWNER_ALT} / {APT_OWNER}  Karim Hossain')
        self.stdout.write(f'  Mess owner:      {MESS_OWNER} / {MESS_OWNER_ALT}  Abdul Karim')
        self.stdout.write(f'  Hotel owner:     {HOTEL_OWNER}  Tanvir Hasan')
        self.stdout.write(f'  Renter:          {RENTERS[0]}  Rahim Uddin')
