"""Seed Phase 7 renter tools demo data."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Role, User, UserProfile
from billing.models import Bill
from documents.models import Checklist, RentalAgreement
from messaging.models import Chat, ChatMessage, MessageStatus, MessageType, Notification
from portfolio.models import Building, Flat
from reports.constants import DEFAULT_REMINDER_SETTINGS, EXPENSE_CATEGORY_SEED
from reports.models import ExpenseCategory, ExpenseReport, Reminder, ReminderSettings
from reports.services.expenses import ensure_default_budgets
from support.models import Complaint, ComplaintStatus


class Command(BaseCommand):
    help = 'Seed complaints, chats, agreements, checklists, expenses, and reminders for demo users.'

    def handle(self, *args, **options):
        owner_phone = '+8801712345678'
        renter_phone = '+8801710000001'

        owner = User.objects.filter(phone=owner_phone).first()
        if not owner:
            self.stdout.write(self.style.WARNING(
                f'Owner {owner_phone} not found — run seed_portfolio or seed_mess first.',
            ))
            return

        renter, _ = User.objects.get_or_create(
            phone=renter_phone,
            defaults={
                'name': 'Rahim Uddin',
                'email': 'rahim.demo@example.com',
                'role': Role.RENTER,
                'is_phone_verified': True,
                'role_selected': True,
            },
        )
        UserProfile.objects.get_or_create(user=renter)

        building = Building.objects.filter(owner=owner).order_by('created_at').first()
        flat = None
        if building:
            flat = Flat.objects.filter(building=building).order_by('flat_number').first()

        # Expense categories
        for cat in EXPENSE_CATEGORY_SEED:
            ExpenseCategory.objects.update_or_create(
                code=cat['code'],
                defaults={
                    'name': cat['name'],
                    'type': cat['type'],
                    'color': cat['color'],
                },
            )
        ensure_default_budgets(renter)

        # Complaints
        c1, _ = Complaint.objects.update_or_create(
            user=renter,
            title='Water leakage in bathroom',
            defaults={
                'user_name': renter.name,
                'description': 'There is a persistent water leak under the bathroom sink.',
                'status': ComplaintStatus.OPEN,
            },
        )
        c2, _ = Complaint.objects.update_or_create(
            user=renter,
            title='Broken elevator',
            defaults={
                'user_name': renter.name,
                'description': 'Elevator has been out of service for 3 days.',
                'status': ComplaintStatus.IN_PROGRESS,
                'response': 'Technician scheduled for tomorrow.',
            },
        )

        # Chat between owner and renter
        p1, p2 = sorted([owner, renter], key=lambda u: str(u.id))
        chat, _ = Chat.objects.update_or_create(
            participant1=p1,
            participant2=p2,
            defaults={
                'participant1_name': p1.name or p1.phone,
                'participant2_name': p2.name or p2.phone,
                'property_id': building.id if building else None,
                'property_name': building.name if building else '',
                'last_message': 'Thank you, I will check the leak tomorrow.',
                'last_message_time': timezone.now(),
                'unread_count_p1': 0,
                'unread_count_p2': 1,
            },
        )
        ChatMessage.objects.filter(chat=chat).delete()
        msgs = [
            (owner, renter, 'Hello, I received your complaint about the bathroom leak.'),
            (renter, owner, 'Yes, it has been leaking for two days now.'),
            (owner, renter, 'Thank you, I will check the leak tomorrow.'),
        ]
        for sender, receiver, content in msgs:
            ChatMessage.objects.create(
                chat=chat,
                sender=sender,
                receiver=receiver,
                type=MessageType.TEXT,
                content=content,
                status=MessageStatus.DELIVERED if receiver == owner else MessageStatus.SENT,
            )

        # Notifications for renter
        Notification.objects.filter(user=renter).delete()
        n1 = Notification.objects.create(
            user=renter,
            title='Complaint Update',
            message='Your complaint "Water leakage in bathroom" is being reviewed.',
            type='complaint',
            link='',
        )
        n2 = Notification.objects.create(
            user=renter,
            title='New Message',
            message=f'You have a new message from {owner.name or owner.phone}.',
            type='system',
        )

        # Rental agreement
        agreement = None
        if building and flat:
            agreement, _ = RentalAgreement.objects.update_or_create(
                user=renter,
                property_id=building.id,
                flat_id=flat.id,
                defaults={
                    'property_name': building.name,
                    'flat_number': flat.flat_number,
                    'agreement_type': 'rental',
                    'start_date': date(2024, 1, 15),
                    'end_date': date(2025, 1, 14),
                    'monthly_rent': Decimal('12000'),
                    'security_deposit': Decimal('30000'),
                    'document_url': '/media/agreements/sample-rental.pdf',
                    'document_name': 'rental-agreement.pdf',
                    'document_size': 245760,
                    'uploaded_by': str(renter.id),
                    'expiry_date': date(2025, 1, 14),
                    'renewal_reminder_days': [30, 15, 7],
                    'status': 'active',
                    'terms': {
                        'duration': 12,
                        'noticePeriod': 30,
                        'renewalTerms': 'Renewable with 30 days notice',
                        'specialConditions': ['No pets', 'No subletting'],
                    },
                },
            )

            checklist, _ = Checklist.objects.update_or_create(
                user=renter,
                property_id=building.id,
                flat_id=flat.id,
                type='move_in',
                defaults={
                    'property_name': building.name,
                    'flat_number': flat.flat_number,
                    'completed_at': timezone.now(),
                    'completed_by': str(renter.id),
                    'items': [
                        {
                            'id': 'item1',
                            'category': 'Living Room',
                            'name': 'Sofa',
                            'status': 'good',
                            'notes': 'Clean and in good condition',
                            'photos': ['/photos/move-in/sofa-1.jpg'],
                            'estimatedValue': 25000,
                        },
                        {
                            'id': 'item2',
                            'category': 'Kitchen',
                            'name': 'Refrigerator',
                            'status': 'good',
                            'notes': 'Working perfectly',
                            'estimatedValue': 35000,
                        },
                    ],
                    'photos': ['/photos/move-in/overview-1.jpg'],
                    'notes': 'Overall condition is good.',
                    'total_estimated_value': Decimal('60000'),
                    'security_deposit_amount': Decimal('30000'),
                    'status': 'approved',
                    'approved_by': str(owner.id),
                    'approved_at': timezone.now(),
                },
            )
        else:
            checklist = None

        # Reminder settings & reminders
        ReminderSettings.objects.update_or_create(
            user=renter,
            defaults={
                'rent_reminders': DEFAULT_REMINDER_SETTINGS['rentReminders'],
                'bill_reminders': DEFAULT_REMINDER_SETTINGS['billReminders'],
                'maintenance_reminders': DEFAULT_REMINDER_SETTINGS['maintenanceReminders'],
                'custom_reminders': DEFAULT_REMINDER_SETTINGS['customReminders'],
            },
        )
        Reminder.objects.filter(user=renter).delete()
        bill = Bill.objects.filter(tenant=renter, is_deleted=False).first()
        bill_id = str(bill.id) if bill else ''
        r1 = Reminder.objects.create(
            user=renter,
            type='rent_due',
            title='Rent Due Reminder',
            message='Your rent is due in 7 days.',
            scheduled_date=timezone.now() + timedelta(days=7),
            channels=['sms', 'push', 'email'],
            status='pending',
            related_entity_id=bill_id,
            related_entity_type='bill',
        )
        r2 = Reminder.objects.create(
            user=renter,
            type='bill_due',
            title='Bill Payment Reminder',
            message='Your electricity bill is due in 5 days.',
            scheduled_date=timezone.now() + timedelta(days=5),
            channels=['push', 'email'],
            status='pending',
            related_entity_id=bill_id,
            related_entity_type='bill',
        )

        # Sample expense report
        report = None
        if bill:
            report, _ = ExpenseReport.objects.update_or_create(
                user=renter,
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
                defaults={
                    'report_type': 'expense',
                    'generated_by': str(renter.id),
                    'data': {
                        'totalExpenses': float(bill.amount),
                        'categoryBreakdown': [],
                        'monthlyBreakdown': [],
                        'bills': [str(bill.id)],
                    },
                    'format': 'pdf',
                    'file_name': 'expense-report-2024.pdf',
                },
            )

        self.stdout.write(self.style.SUCCESS('Phase 7 seed complete — IDs:'))
        self.stdout.write(f'  owner_phone={owner.phone} owner_id={owner.id}')
        self.stdout.write(f'  renter_phone={renter.phone} renter_id={renter.id}')
        self.stdout.write(f'  complaint_ids={[str(c1.id), str(c2.id)]}')
        self.stdout.write(f'  chat_id={chat.id}')
        if agreement:
            self.stdout.write(f'  agreement_id={agreement.id}')
        if checklist:
            self.stdout.write(f'  checklist_id={checklist.id}')
        self.stdout.write(f'  notification_ids={[str(n1.id), str(n2.id)]}')
        self.stdout.write(f'  reminder_ids={[str(r1.id), str(r2.id)]}')
        if report:
            self.stdout.write(f'  expense_report_id={report.id}')
