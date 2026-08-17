"""Seed admin tools demo data for Phase 8."""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.models import Role, User, VerificationDocument
from admin_api.models import (
    ActivityLog,
    ActivityResourceType,
    Dispute,
    DisputePriority,
    DisputeStatus,
    DisputeType,
    FraudReport,
    FraudReportStatus,
    FraudReportType,
)
from admin_api.services import ensure_system_settings
from audit.models import AuditAction, AuditEntityType, AuditLog
from audit.services import create_audit_log
from support.models import Complaint, ComplaintStatus


class Command(BaseCommand):
    help = 'Seed admin dashboard tools: disputes, fraud reports, settings, audit logs'

    def handle(self, *args, **options):
        call_command('seed_demo_admins')

        admin = User.objects.filter(role=Role.ADMIN).first()
        renter = User.objects.filter(role=Role.RENTER).first()
        owner = User.objects.filter(role=Role.OWNER).first()

        settings_obj = ensure_system_settings()
        self.stdout.write(self.style.SUCCESS(f'SystemSettings ready: {settings_obj.platform_name}'))

        if renter and not VerificationDocument.objects.filter(
            user=renter,
            status=VerificationDocument.Status.PENDING,
        ).exists():
            VerificationDocument.objects.create(
                user=renter,
                verification_type=VerificationDocument.VerificationType.NID,
                document_number='1234567890123',
                file_name='demo-nid.pdf',
                status=VerificationDocument.Status.PENDING,
            )
            self.stdout.write(self.style.SUCCESS(f'Created pending verification for {renter.phone}'))

        if admin and renter:
            dispute, created = Dispute.objects.get_or_create(
                title='Payment Dispute - Demo Booking',
                defaults={
                    'description': 'Guest claims payment was made but booking shows unpaid.',
                    'type': DisputeType.PAYMENT,
                    'status': DisputeStatus.OPEN,
                    'priority': DisputePriority.HIGH,
                    'created_by': renter,
                    'created_by_name': renter.name or renter.phone,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created dispute: {dispute.title}'))

            in_progress, ip_created = Dispute.objects.get_or_create(
                title='Property Misrepresentation - Demo',
                defaults={
                    'description': 'Renter claims property does not match listing description.',
                    'type': DisputeType.PROPERTY,
                    'status': DisputeStatus.IN_PROGRESS,
                    'priority': DisputePriority.MEDIUM,
                    'created_by': renter,
                    'created_by_name': renter.name or renter.phone,
                    'assigned_to': admin,
                    'assigned_to_name': admin.name or admin.phone,
                },
            )
            if ip_created:
                self.stdout.write(self.style.SUCCESS(f'Created dispute: {in_progress.title}'))

        if renter:
            fraud, f_created = FraudReport.objects.get_or_create(
                user=renter,
                report_type=FraudReportType.FAKE_LISTING,
                description='Property images appear copied from another site.',
                defaults={
                    'user_name': renter.name or renter.phone,
                    'status': FraudReportStatus.INVESTIGATING,
                    'priority': DisputePriority.HIGH,
                    'investigated_by': admin,
                },
            )
            if f_created:
                self.stdout.write(self.style.SUCCESS(f'Created fraud report: {fraud.id}'))

            fraud2, f2_created = FraudReport.objects.get_or_create(
                user=renter,
                report_type=FraudReportType.PAYMENT_FRAUD,
                description='Multiple failed payment attempts with different cards.',
                defaults={
                    'user_name': renter.name or renter.phone,
                    'status': FraudReportStatus.PENDING,
                    'priority': DisputePriority.URGENT,
                },
            )
            if f2_created:
                self.stdout.write(self.style.SUCCESS(f'Created fraud report: {fraud2.id}'))

            if not Complaint.objects.filter(user=renter, is_deleted=False).exists():
                Complaint.objects.create(
                    user=renter,
                    user_name=renter.name or renter.phone,
                    title='Broken AC in flat',
                    description='Air conditioner stopped working two days ago.',
                    status=ComplaintStatus.OPEN,
                )
                Complaint.objects.create(
                    user=renter,
                    user_name=renter.name or renter.phone,
                    title='Noise complaint',
                    description='Construction noise after 10pm from neighboring unit.',
                    status=ComplaintStatus.IN_PROGRESS,
                )
                self.stdout.write(self.style.SUCCESS('Created demo complaints for admin queue'))

        if renter:
            ActivityLog.objects.get_or_create(
                user=renter,
                action='created',
                resource_type=ActivityResourceType.BOOKING,
                resource_id='demo-booking-1',
                defaults={
                    'user_name': renter.name or renter.phone,
                    'details': 'Created demo booking via seed_admin_tools',
                    'ip_address': '127.0.0.1',
                },
            )

        if admin and not AuditLog.objects.exists():
            create_audit_log(
                admin,
                action=AuditAction.APPROVE,
                entity_type=AuditEntityType.VERIFICATION,
                entity_id='seed-verification',
                entity_name='Demo verification approval',
                changes=[{
                    'field': 'status',
                    'oldValue': 'pending',
                    'newValue': 'approved',
                }],
                can_rollback=True,
                rollback_data={
                    'entity_type': 'verification',
                    'entity_id': 'seed-verification',
                    'fields': {'status': 'pending'},
                },
            )
            if owner:
                create_audit_log(
                    admin,
                    action=AuditAction.UPDATE,
                    entity_type=AuditEntityType.PROPERTY,
                    entity_id=str(owner.id),
                    entity_name='Demo property moderation',
                    metadata={'seed': True},
                )

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Seed counts:'))
        self.stdout.write(f'  Admins: {User.objects.filter(role=Role.ADMIN).count()}')
        self.stdout.write(f'  Disputes: {Dispute.objects.count()}')
        self.stdout.write(f'  FraudReports: {FraudReport.objects.count()}')
        self.stdout.write(f'  Complaints: {Complaint.objects.filter(is_deleted=False).count()}')
        self.stdout.write(f'  ActivityLogs: {ActivityLog.objects.count()}')
        self.stdout.write(f'  AuditLogs: {AuditLog.objects.count()}')
        self.stdout.write(
            f'  Pending verifications: '
            f'{VerificationDocument.objects.filter(status=VerificationDocument.Status.PENDING).count()}',
        )
