"""Seed sample messes for local / demo testing (ops + public profiles)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Role, User, UserProfile
from mess.models import (
    AttendanceRecord,
    AttendanceStatus,
    AttendanceType,
    DailyMenu,
    DEFAULT_MEAL_TIMING,
    MealTiming,
    MemberMealLog,
    Mess,
    MessExpense,
    MessNotice,
    MessRule,
    MessStudent,
    OccupantType,
    Seat,
    SeatStatus,
    SMSGroup,
    SMSTemplate,
    WeeklySchedule,
)
from mess.services.live_status import DEFAULT_LIVE_STATUS
from mess.calendar_bd import bangladesh_week_bounds


SEED_MESS_NAMES = (
    'Green Valley Mess',
    'Dhanmondi Ladies Hostel',
    'Mohammadpur Campus Mess',
    'Uttara Tech Mess',
)

# Shared seat layout reused per mess
DEFAULT_SEATS = [
    {'seat_number': 'A-01', 'room_number': 'Room A', 'status': SeatStatus.OCCUPIED},
    {'seat_number': 'A-02', 'room_number': 'Room A', 'status': SeatStatus.OCCUPIED},
    {'seat_number': 'A-03', 'room_number': 'Room A', 'status': SeatStatus.AVAILABLE},
    {'seat_number': 'B-01', 'room_number': 'Room B', 'status': SeatStatus.AVAILABLE},
    {'seat_number': 'B-02', 'room_number': 'Room B', 'status': SeatStatus.AVAILABLE},
    {'seat_number': 'B-03', 'room_number': 'Room B', 'status': SeatStatus.AVAILABLE},
]

MESS_SPECS = [
    {
        'name': 'Green Valley Mess',
        'owner_phone': '+8801712345678',
        'owner_name': 'Abdul Karim',
        'address': 'House 45, Road 7, Block C, Mirpur-10',
        'city': 'Dhaka',
        'monthly_fee': Decimal('3500'),
        'gender': 'male',
        'facilities': [
            'WiFi', 'AC', 'Generator', 'Security', 'Parking', 'Common Kitchen', 'Meal',
        ],
        'images': [
            'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800',
            'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800',
        ],
        'description': (
            'Clean and spacious mess with modern amenities. '
            'Perfect for students and working professionals.'
        ),
        'meals_per_day': 3,
        'vegetarian_option': False,
        'guest_meal_price': Decimal('60'),
        'meal_monthly_charge': Decimal('2500'),
        'fish_meat_days_per_week': 5,
        'meal_off_policy': 'Notify manager 12 hours before meal-off.',
        'water_profile': {
            'availability': '24_7',
            'source': 'wasa',
            'hasFilter': True,
            'separateDrinkingWater': True,
            'hasBackup': True,
            'tankCapacityLiters': 2000,
        },
        'electricity_profile': {
            'availability': '24_7',
            'loadSheddingLevel': 'rare',
            'hasIps': True,
            'hasGenerator': True,
            'commonAreaBackup': True,
            'emergencyLight': True,
            'meterType': 'shared',
            'billSplitMethod': 'equal',
        },
        'seats': [
            {'seat_number': 'A-01', 'room_number': 'Room A', 'status': SeatStatus.OCCUPIED},
            {'seat_number': 'A-02', 'room_number': 'Room A', 'status': SeatStatus.OCCUPIED},
            {'seat_number': 'A-03', 'room_number': 'Room A', 'status': SeatStatus.OCCUPIED},
            {'seat_number': 'B-01', 'room_number': 'Room B', 'status': SeatStatus.AVAILABLE},
            {'seat_number': 'B-02', 'room_number': 'Room B', 'status': SeatStatus.AVAILABLE},
            {'seat_number': 'B-03', 'room_number': 'Room B', 'status': SeatStatus.AVAILABLE},
        ],
        'students': [
            {
                'name': 'Rahim Uddin',
                'phone': '+8801710000001',
                'email': 'rahim@example.com',
                'student_id_code': 'STU-2024-001',
                'university': 'Dhaka University',
                'seat_number': 'A-01',
            },
            {
                'name': 'Karim Ahmed',
                'phone': '+8801710000003',
                'email': 'imran.hossain@gmail.com',
                'student_id_code': 'STU-2024-002',
                'university': 'BUET',
                'seat_number': 'A-02',
            },
            {
                'name': 'Mehedi Hasan',
                'phone': '+8801710000007',
                'email': 'mehedi.hasan@gmail.com',
                'occupant_type': OccupantType.JOB_HOLDER,
                'organization': 'Brain Station 23',
                'designation': 'Software Engineer',
                'seat_number': 'A-03',
            },
        ],
        'menu_lunch': 'Chicken Biryani',
        'grocery_amount': Decimal('15000'),
        'grocery_vendor': 'Karwan Bazar',
    },
    {
        'name': 'Dhanmondi Ladies Hostel',
        'owner_phone': '+8801712345679',
        'owner_name': 'Fatema Begum',
        'address': 'Road 8, House 12, Dhanmondi',
        'city': 'Dhaka',
        'monthly_fee': Decimal('5500'),
        'gender': 'female',
        'facilities': [
            'WiFi', 'Attached Bath', 'CCTV', 'Generator', 'Filter Water',
            'Laundry', '3 Meals', 'Security Guard',
        ],
        'images': [
            'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800',
            'https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=800',
        ],
        'description': (
            'Safe ladies hostel near Dhanmondi Lake and multiple universities. '
            'CCTV, female caretaker, and home-style meals included.'
        ),
        'meals_per_day': 3,
        'vegetarian_option': True,
        'guest_meal_price': Decimal('80'),
        'meal_monthly_charge': Decimal('3200'),
        'fish_meat_days_per_week': 4,
        'meal_off_policy': 'Meal-off must be requested one day ahead via the app.',
        'water_profile': {
            'availability': '24_7',
            'source': 'both',
            'hasFilter': True,
            'separateDrinkingWater': True,
            'hasBackup': True,
            'tankCapacityLiters': 3000,
        },
        'electricity_profile': {
            'availability': '24_7',
            'loadSheddingLevel': 'rare',
            'hasIps': True,
            'hasGenerator': True,
            'liftBackup': False,
            'commonAreaBackup': True,
            'emergencyLight': True,
            'meterType': 'shared',
            'billSplitMethod': 'equal',
        },
        'seats': list(DEFAULT_SEATS),
        'students': [
            {
                'name': 'Nusrat Jahan',
                'phone': '+8801710000002',
                'email': 'nusrat@example.com',
                'student_id_code': 'DLH-2024-01',
                'university': 'Dhaka University',
                'seat_number': 'A-01',
            },
            {
                'name': 'Sadia Islam',
                'phone': '+8801710000004',
                'email': 'sadia@example.com',
                'student_id_code': 'DLH-2024-02',
                'university': 'NSU',
                'seat_number': 'A-02',
            },
        ],
        'menu_lunch': 'Vegetable Khichuri & Egg',
        'grocery_amount': Decimal('12000'),
        'grocery_vendor': 'Dhanmondi Kitchen Market',
    },
    {
        'name': 'Mohammadpur Campus Mess',
        'owner_phone': '+8801712345681',
        'owner_name': 'Shahidul Islam',
        'address': 'Block C, Road 3, Mohammadpur Housing',
        'city': 'Dhaka',
        'monthly_fee': Decimal('4200'),
        'gender': 'male',
        'facilities': [
            'WiFi', 'Generator', 'Study Room', 'Common Kitchen',
            'Parking', 'Meal', 'Water Filter',
        ],
        'images': [
            'https://images.unsplash.com/photo-1555854877-bab0e564b8d5?w=800',
            'https://images.unsplash.com/photo-1522771739844-6a9f6d5f14af?w=800',
        ],
        'description': (
            'Budget-friendly student mess near Mohammadpur bus stand. '
            'Walking distance to several coaching centers and markets.'
        ),
        'meals_per_day': 2,
        'vegetarian_option': False,
        'guest_meal_price': Decimal('50'),
        'meal_monthly_charge': Decimal('1800'),
        'fish_meat_days_per_week': 3,
        'meal_off_policy': 'Lunch/dinner off if requested before 9 AM.',
        'water_profile': {
            'availability': 'limited',
            'source': 'deep_tube',
            'hasFilter': True,
            'separateDrinkingWater': False,
            'hasBackup': False,
            'tankCapacityLiters': 1000,
        },
        'electricity_profile': {
            'availability': '24_7',
            'loadSheddingLevel': 'moderate',
            'hasIps': False,
            'hasGenerator': True,
            'commonAreaBackup': True,
            'emergencyLight': True,
            'meterType': 'shared',
            'billSplitMethod': 'equal',
        },
        'seats': list(DEFAULT_SEATS),
        'students': [
            {
                'name': 'Tanvir Rahman',
                'phone': '+8801710000005',
                'email': 'tanvir@example.com',
                'student_id_code': 'MCM-2024-01',
                'university': 'IUT',
                'seat_number': 'A-01',
            },
            {
                'name': 'Rakib Hasan',
                'phone': '+8801710000006',
                'email': 'rakib@example.com',
                'occupant_type': OccupantType.BUSINESS,
                'organization': 'Rakib Electronics, New Market',
                'seat_number': 'A-02',
            },
        ],
        'menu_lunch': 'Dal, Bhorta & Rice',
        'grocery_amount': Decimal('9000'),
        'grocery_vendor': 'Town Hall Bazar',
    },
    {
        'name': 'Uttara Tech Mess',
        'owner_phone': '+8801812345678',
        'owner_name': 'Rafiqul Alam',
        'address': 'Sector 7, Road 12, Uttara',
        'city': 'Dhaka',
        'monthly_fee': Decimal('6500'),
        'gender': 'mixed',
        'facilities': [
            'WiFi', 'AC', 'IPS', 'Generator', 'CCTV', 'Lift',
            'Attached Bath', '3 Meals', 'Parking',
        ],
        'images': [
            'https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?w=800',
            'https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=800',
        ],
        'description': (
            'Premium mess for IT professionals and students in Uttara. '
            'High-speed Wi‑Fi, backup power, and guest meal options.'
        ),
        'meals_per_day': 3,
        'vegetarian_option': True,
        'guest_meal_price': Decimal('100'),
        'meal_monthly_charge': Decimal('4000'),
        'fish_meat_days_per_week': 6,
        'meal_off_policy': 'Guest meals must be booked by 6 PM previous day.',
        'water_profile': {
            'availability': '24_7',
            'source': 'wasa',
            'hasFilter': True,
            'separateDrinkingWater': True,
            'hasBackup': True,
            'tankCapacityLiters': 5000,
        },
        'electricity_profile': {
            'availability': '24_7',
            'loadSheddingLevel': 'rare',
            'hasIps': True,
            'hasGenerator': True,
            'liftBackup': True,
            'commonAreaBackup': True,
            'emergencyLight': True,
            'meterType': 'separate',
            'billSplitMethod': 'meter',
        },
        'seats': list(DEFAULT_SEATS),
        'students': [
            {
                'name': 'Arif Chowdhury',
                'phone': '+8801710000008',
                'email': 'arif@example.com',
                'student_id_code': 'UTM-2024-01',
                'university': 'AIUB',
                'seat_number': 'A-01',
            },
            {
                'name': 'Farhana Akter',
                'phone': '+8801512345678',
                'email': 'farhana@example.com',
                'occupant_type': OccupantType.JOB_HOLDER,
                'organization': 'BRAC Bank, Uttara Branch',
                'designation': 'Relationship Officer',
                'seat_number': 'A-02',
            },
        ],
        'menu_lunch': 'Grilled Chicken & Salad',
        'grocery_amount': Decimal('18000'),
        'grocery_vendor': 'Uttara Sector 10 Bazar',
    },
]


class Command(BaseCommand):
    help = (
        'Seed Green Valley Mess plus Dhanmondi / Mohammadpur / Uttara demo messes '
        'with seats, students, menus, expenses, and utility profiles.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete previously seeded demo messes before seeding.',
        )

    def handle(self, *args, **options):
        if options['flush']:
            deleted, _ = Mess.objects.filter(name__in=SEED_MESS_NAMES).delete()
            self.stdout.write(
                self.style.WARNING(f'Flushed seeded mess rows (cascade count≈{deleted}).'),
            )

        for spec in MESS_SPECS:
            mess = self._seed_mess(spec)
            self.stdout.write(
                self.style.SUCCESS(
                    f"OK {mess.name} (id={mess.id}) | "
                    f'{mess.city} | {mess.gender} | '
                    f'{mess.available_seats}/{mess.total_seats} seats open | '
                    f'guest meal={mess.guest_meal_price}',
                ),
            )

        self.stdout.write(self.style.SUCCESS(f'Seeded {len(MESS_SPECS)} messes.'))
        self.stdout.write('Browse: http://localhost:3000/messes')

    def _ensure_owner(self, phone: str, name: str) -> User:
        owner, _ = User.objects.get_or_create(
            phone=phone,
            defaults={
                'name': name,
                'role': Role.OWNER,
                'role_selected': True,
                'is_phone_verified': True,
                'whatsapp_number': phone,
            },
        )
        if owner.role != Role.OWNER:
            owner.role = Role.OWNER
            owner.role_selected = True
            owner.is_phone_verified = True
            if not owner.name:
                owner.name = name
            owner.save(
                update_fields=['role', 'role_selected', 'is_phone_verified', 'name', 'updated_at'],
            )
        UserProfile.objects.get_or_create(user=owner)
        return owner

    def _seed_mess(self, spec: dict) -> Mess:
        owner = self._ensure_owner(spec['owner_phone'], spec['owner_name'])
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)

        mess, _created = Mess.objects.update_or_create(
            owner=owner,
            name=spec['name'],
            defaults={
                'address': spec['address'],
                'city': spec['city'],
                'monthly_fee': spec['monthly_fee'],
                'gender': spec['gender'],
                'facilities': spec['facilities'],
                'images': spec['images'],
                'description': spec['description'],
                'is_deleted': False,
                'meals_per_day': spec['meals_per_day'],
                'vegetarian_option': spec['vegetarian_option'],
                'guest_meal_price': spec['guest_meal_price'],
                'meal_monthly_charge': spec['meal_monthly_charge'],
                'fish_meat_days_per_week': spec['fish_meat_days_per_week'],
                'meal_off_policy': spec['meal_off_policy'],
                'water_profile': spec['water_profile'],
                'electricity_profile': spec['electricity_profile'],
                'live_status': dict(DEFAULT_LIVE_STATUS),
                'live_status_updated_at': timezone.now(),
                'last_confirmed_at': timezone.now(),
            },
        )

        seats: dict[str, Seat] = {}
        for seat_spec in spec['seats']:
            seat, _ = Seat.objects.update_or_create(
                mess=mess,
                seat_number=seat_spec['seat_number'],
                defaults={
                    'room_number': seat_spec['room_number'],
                    'status': seat_spec['status'],
                    'is_deleted': False,
                },
            )
            seats[seat_spec['seat_number']] = seat

        student_objs: list[MessStudent] = []
        for stu in spec['students']:
            from accounts.phone import normalize_bd_phone

            phone = normalize_bd_phone(stu['phone'])
            user = User.objects.filter(phone=phone).first()
            student, _ = MessStudent.objects.update_or_create(
                mess=mess,
                phone=phone,
                defaults={
                    'user': user,
                    'name': stu['name'],
                    'whatsapp_number': normalize_bd_phone(
                        stu.get('whatsapp_number') or stu['phone'],
                    ),
                    'email': stu.get('email') or '',
                    'occupant_type': stu.get('occupant_type') or OccupantType.STUDENT,
                    'student_id_code': stu.get('student_id_code') or '',
                    'university': stu.get('university') or '',
                    'organization': stu.get('organization') or '',
                    'designation': stu.get('designation') or '',
                    'seat_number': stu['seat_number'],
                    'joined_date': date(2024, 1, 15),
                    'monthly_fee': spec['monthly_fee'],
                    'is_active': True,
                    'is_deleted': False,
                },
            )
            seat = seats.get(stu['seat_number'])
            if seat:
                seat.status = SeatStatus.OCCUPIED
                seat.student = student
                seat.save(update_fields=['status', 'student', 'updated_at'])
                student.seat = seat
                student.seat_number = seat.seat_number
                student.save(update_fields=['seat', 'seat_number', 'updated_at'])
            student_objs.append(student)

        mess.refresh_seat_counts()

        lunch_name = spec.get('menu_lunch') or 'Rice & Curry'
        for menu_date, label in ((today, 'today'), (tomorrow, 'tomorrow')):
            DailyMenu.objects.update_or_create(
                mess=mess,
                date=menu_date,
                defaults={
                    'breakfast': [
                        {
                            'id': f'{mess.id}-bf-{label}',
                            'name': 'Paratha & Egg',
                            'description': 'Fresh paratha with fried egg',
                        },
                    ],
                    'lunch': [
                        {
                            'id': f'{mess.id}-ln-{label}',
                            'name': lunch_name,
                            'description': f'Seed lunch for {mess.name}',
                            'isSpecial': label == 'today',
                        },
                    ],
                    'dinner': [
                        {
                            'id': f'{mess.id}-dn-{label}',
                            'name': 'Fish Curry & Rice',
                            'description': 'Seasonal fish with steamed rice',
                        },
                    ],
                    'snack': [
                        {'id': f'{mess.id}-sn-{label}', 'name': 'Tea & Biscuit'},
                    ],
                    'notes': f'Seed menu for {label}',
                    'created_by': owner,
                },
            )

        MealTiming.objects.get_or_create(
            mess=mess,
            defaults={
                'breakfast': DEFAULT_MEAL_TIMING['breakfast'],
                'lunch': DEFAULT_MEAL_TIMING['lunch'],
                'dinner': DEFAULT_MEAL_TIMING['dinner'],
                'snack': DEFAULT_MEAL_TIMING['snack'],
            },
        )

        week_start, week_end = bangladesh_week_bounds(today)
        WeeklySchedule.objects.update_or_create(
            mess=mess,
            week_start_date=week_start,
            defaults={
                'week_end_date': week_end,
                'schedule': {
                    'saturday': {
                        'lunch': [{'id': 'sat-ln', 'name': lunch_name}],
                        'dinner': [{'id': 'sat-dn', 'name': 'Dal & Rice'}],
                    },
                    'sunday': {
                        'breakfast': [{'id': 'sun-bf', 'name': 'Khichuri'}],
                        'lunch': [{'id': 'sun-ln', 'name': 'Chicken Curry'}],
                    },
                    'monday': {
                        'breakfast': [{'id': 'mon-bf', 'name': 'Khichuri'}],
                        'lunch': [{'id': 'mon-ln', 'name': lunch_name}],
                        'dinner': [{'id': 'mon-dn', 'name': 'Dal & Rice'}],
                    },
                    'tuesday': {
                        'lunch': [{'id': 'tue-ln', 'name': 'Chicken Roast'}],
                        'dinner': [{'id': 'tue-dn', 'name': 'Vegetable Curry'}],
                    },
                    'wednesday': {
                        'lunch': [{'id': 'wed-ln', 'name': 'Beef Curry'}],
                    },
                },
                'is_active': True,
                'created_by': owner,
            },
        )

        MessNotice.objects.get_or_create(
            mess=mess,
            title='Monthly Fee Payment Reminder',
            defaults={
                'content': (
                    f'Please pay your monthly fee (৳{spec["monthly_fee"]}) by the 5th. '
                    'Late payment may incur a fine.'
                ),
                'date': today,
                'priority': 'high',
                'category': 'payment',
                'expiry_date': today + timedelta(days=30),
                'created_by': owner,
            },
        )
        MessNotice.objects.get_or_create(
            mess=mess,
            title=f'{mess.name} house meeting',
            defaults={
                'content': 'General meeting this week at 7 PM. All members please attend.',
                'date': today,
                'priority': 'medium',
                'category': 'event',
                'created_by': owner,
            },
        )

        if student_objs:
            AttendanceRecord.objects.get_or_create(
                mess=mess,
                student=student_objs[0],
                date=today,
                defaults={
                    'student_name': student_objs[0].name,
                    'status': AttendanceStatus.PRESENT,
                    'type': AttendanceType.GENERAL,
                    'marked_by': owner,
                    'marked_at': timezone.now(),
                },
            )

        SMSTemplate.objects.get_or_create(
            mess=mess,
            name='Payment Reminder',
            defaults={
                'content': 'Dear {name}, please pay your mess fee of ৳{amount} by {date}.',
                'variables': ['{name}', '{date}', '{amount}'],
                'category': 'payment',
                'created_by': owner,
            },
        )

        if student_objs:
            SMSGroup.objects.update_or_create(
                mess=mess,
                name='All Students',
                defaults={
                    'description': f'All active students in {mess.name}',
                    'member_ids': [str(s.id) for s in student_objs],
                    'created_by': owner,
                    'is_deleted': False,
                },
            )

        MessRule.objects.get_or_create(
            mess=mess,
            title='Quiet Hours',
            defaults={
                'description': 'Maintain silence between 10 PM and 6 AM.',
                'category': 'behavior',
                'severity': 'moderate',
                'penalty': 'Fine: ৳500',
                'status': 'active',
                'requires_acceptance': True,
                'created_by': owner,
            },
        )

        # Day-by-day meals so মিল হিসাব and the member meal sheet have real data
        for index, student in enumerate(student_objs):
            for offset in range(today.day):
                day = today.replace(day=1) + timedelta(days=offset)
                # Vary the pattern per member/day: some skip breakfast, some
                # bring an occasional guest.
                skew = (index + offset) % 5
                MemberMealLog.objects.update_or_create(
                    mess=mess,
                    student=student,
                    date=day,
                    defaults={
                        'breakfast': Decimal('0') if skew == 0 else Decimal('1'),
                        'lunch': Decimal('1'),
                        'dinner': Decimal('0') if skew == 4 else Decimal('1'),
                        'guest_lunch': 1 if skew == 2 and offset % 7 == 0 else 0,
                        'notes': 'Guest joined lunch' if skew == 2 and offset % 7 == 0 else '',
                        'marked_by': owner,
                    },
                )

        MessExpense.objects.get_or_create(
            mess=mess,
            description='Weekly grocery purchase',
            date=today.replace(day=1),
            defaults={
                'category': 'food',
                'amount': spec['grocery_amount'],
                'vendor': spec['grocery_vendor'],
                'notes': 'Seed bazaar cost for মিল হিসাব',
                'created_by': owner,
                'is_deleted': False,
            },
        )
        MessExpense.objects.get_or_create(
            mess=mess,
            description='Utilities share',
            date=today.replace(day=1),
            defaults={
                'category': 'utilities',
                'amount': Decimal('2500'),
                'vendor': 'WASA / DESCO',
                'notes': 'Seed fixed cost',
                'created_by': owner,
                'is_deleted': False,
            },
        )

        # Public listing mirror for book-bridge testing
        try:
            from listings.services.inventory import ensure_listing_for_mess

            ensure_listing_for_mess(mess)
        except Exception as exc:  # pragma: no cover - seed should not fail hard
            self.stdout.write(
                self.style.WARNING(f'  listing sync skipped for {mess.name}: {exc}'),
            )

        return mess
