"""Seed sample mess data for Phase 6."""

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
    Mess,
    MessExpense,
    MessNotice,
    MessRule,
    MessStudent,
    Seat,
    SeatStatus,
    SMSGroup,
    SMSTemplate,
    WeeklySchedule,
)


SEATS = [
    {'seat_number': 'A-01', 'room_number': 'Room A', 'status': SeatStatus.OCCUPIED},
    {'seat_number': 'A-02', 'room_number': 'Room A', 'status': SeatStatus.OCCUPIED},
    {'seat_number': 'A-03', 'room_number': 'Room A', 'status': SeatStatus.OCCUPIED},
    {'seat_number': 'B-01', 'room_number': 'Room B', 'status': SeatStatus.AVAILABLE},
    {'seat_number': 'B-02', 'room_number': 'Room B', 'status': SeatStatus.AVAILABLE},
    {'seat_number': 'B-03', 'room_number': 'Room B', 'status': SeatStatus.AVAILABLE},
]

STUDENTS = [
    {
        'name': 'Rahim Uddin',
        'phone': '+8801710000001',
        'email': 'rahim@example.com',
        'student_id_code': 'STU-2024-001',
        'university': 'Dhaka University',
        'seat_number': 'A-01',
        'link_renter': True,
    },
    {
        'name': 'Karim Ahmed',
        'phone': '+8801712345680',
        'email': 'karim@example.com',
        'student_id_code': 'STU-2024-002',
        'university': 'BUET',
        'seat_number': 'A-02',
        'link_renter': False,
    },
    {
        'name': 'Sakib Hasan',
        'phone': '+8801712345682',
        'email': 'sakib@example.com',
        'student_id_code': 'STU-2024-004',
        'university': 'NSU',
        'seat_number': 'A-03',
        'link_renter': False,
    },
]


class Command(BaseCommand):
    help = 'Seed Green Valley Mess with seats, students, menus, and sample data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete existing mess data for the seed owner before seeding.',
        )

    def handle(self, *args, **options):
        owner, _ = User.objects.get_or_create(
            phone='+8801712345678',
            defaults={
                'name': 'Abdul Karim',
                'role': Role.OWNER,
                'role_selected': True,
                'is_phone_verified': True,
            },
        )
        UserProfile.objects.get_or_create(user=owner)

        if options['flush']:
            Mess.objects.filter(owner=owner, name='Green Valley Mess').delete()
            self.stdout.write(self.style.WARNING('Flushed existing Green Valley Mess data.'))

        mess, created = Mess.objects.get_or_create(
            owner=owner,
            name='Green Valley Mess',
            defaults={
                'address': 'House 45, Road 7, Block C, Mirpur-10',
                'city': 'Dhaka',
                'monthly_fee': Decimal('3500'),
                'gender': 'male',
                'facilities': [
                    'WiFi', 'AC', 'Generator', 'Security', 'Parking', 'Common Kitchen',
                ],
                'images': [
                    'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800',
                    'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800',
                ],
                'description': (
                    'Clean and spacious mess with modern amenities. '
                    'Perfect for students and working professionals.'
                ),
            },
        )

        seats = {}
        for spec in SEATS:
            seat, _ = Seat.objects.get_or_create(
                mess=mess,
                seat_number=spec['seat_number'],
                defaults={
                    'room_number': spec['room_number'],
                    'status': spec['status'],
                },
            )
            seats[spec['seat_number']] = seat

        renter = User.objects.filter(phone='+8801710000001').first()
        student_objs = []
        for spec in STUDENTS:
            user = renter if spec.get('link_renter') and renter else None
            student, _ = MessStudent.objects.get_or_create(
                mess=mess,
                phone=spec['phone'],
                defaults={
                    'user': user,
                    'name': spec['name'],
                    'email': spec['email'],
                    'student_id_code': spec['student_id_code'],
                    'university': spec['university'],
                    'seat_number': spec['seat_number'],
                    'joined_date': date(2024, 1, 15),
                    'monthly_fee': Decimal('3500'),
                    'is_active': True,
                },
            )
            seat = seats.get(spec['seat_number'])
            if seat:
                seat.status = SeatStatus.OCCUPIED
                seat.student = student
                seat.save(update_fields=['status', 'student', 'updated_at'])
                student.seat = seat
                student.save(update_fields=['seat', 'updated_at'])
            student_objs.append(student)

        mess.refresh_seat_counts()

        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)

        for menu_date, label in ((today, 'today'), (tomorrow, 'tomorrow')):
            DailyMenu.objects.update_or_create(
                mess=mess,
                date=menu_date,
                defaults={
                    'breakfast': [
                        {
                            'id': f'bf-{label}',
                            'name': 'Paratha & Egg',
                            'description': 'Fresh paratha with fried egg',
                        },
                    ],
                    'lunch': [
                        {
                            'id': f'ln-{label}',
                            'name': 'Chicken Biryani',
                            'description': 'Hyderabadi style biryani',
                            'isSpecial': label == 'today',
                        },
                    ],
                    'dinner': [
                        {
                            'id': f'dn-{label}',
                            'name': 'Fish Curry & Rice',
                            'description': 'Rui fish curry with steamed rice',
                        },
                    ],
                    'snack': [
                        {
                            'id': f'sn-{label}',
                            'name': 'Tea & Biscuit',
                        },
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

        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        WeeklySchedule.objects.get_or_create(
            mess=mess,
            week_start_date=week_start,
            defaults={
                'week_end_date': week_end,
                'schedule': {
                    'monday': {
                        'breakfast': [{'id': 'mon-bf', 'name': 'Khichuri'}],
                        'lunch': [{'id': 'mon-ln', 'name': 'Beef Curry'}],
                        'dinner': [{'id': 'mon-dn', 'name': 'Dal & Rice'}],
                    },
                    'tuesday': {
                        'lunch': [{'id': 'tue-ln', 'name': 'Chicken Roast'}],
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
                    'Please pay your monthly fee by 5th of every month. '
                    'Late payment will incur a fine of ৳200.'
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
            title='Mess Meeting Scheduled',
            defaults={
                'content': (
                    'A general meeting will be held next week at 7 PM. '
                    'All students are requested to attend.'
                ),
                'date': today,
                'priority': 'medium',
                'category': 'event',
                'image_urls': [
                    'https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=800',
                ],
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

        template, _ = SMSTemplate.objects.get_or_create(
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
            SMSGroup.objects.get_or_create(
                mess=mess,
                name='All Students',
                defaults={
                    'description': 'All active students in Green Valley Mess',
                    'member_ids': [str(s.id) for s in student_objs],
                    'created_by': owner,
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

        MessExpense.objects.get_or_create(
            mess=mess,
            description='Weekly grocery purchase',
            date=today.replace(day=1),
            defaults={
                'category': 'food',
                'amount': Decimal('15000'),
                'vendor': 'Karwan Bazar',
                'notes': 'Rice, lentils, vegetables, chicken',
                'created_by': owner,
            },
        )

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{action} Green Valley Mess (id={mess.id})'))
        self.stdout.write(f'  Owner: {owner.name} ({owner.phone})')
        self.stdout.write(f'  Seats: {mess.total_seats} total, {mess.available_seats} available')
        self.stdout.write(f'  Students: {len(student_objs)}')
        if renter:
            self.stdout.write(f'  Linked renter: {renter.name} ({renter.phone})')
        else:
            self.stdout.write('  Linked renter: none (+8801710000001 not found)')
        self.stdout.write(f'  SMS template: {template.name}')
