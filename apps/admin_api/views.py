from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role, User, VerificationDocument
from admin_api.models import (
    ActivityLog,
    Dispute,
    DisputeStatus,
    FraudReport,
    FraudReportStatus,
    SystemSettings,
    UserAccountStatus,
)
from admin_api.permissions import IsPlatformAdmin, admin_has_permission
from admin_api.serializers import (
    ActivityLogSerializer,
    AdminUserSerializer,
    DisputeCreateSerializer,
    DisputePatchSerializer,
    DisputeSerializer,
    FraudReportCreateSerializer,
    FraudReportPatchSerializer,
    FraudReportSerializer,
    PropertyModerationPatchSerializer,
    PropertyModerationSerializer,
    SystemSettingsSerializer,
    UserManagementSerializer,
    UserModerationPatchSerializer,
    VerificationPatchSerializer,
    VerificationRequestSerializer,
)
from admin_api.services import (
    apply_moderation_status,
    compute_analytics,
    ensure_system_settings,
    get_or_create_user_moderation,
    serialize_managed_user,
)
from audit.services import create_audit_log, rollback_audit
from audit.views import filter_audit_logs, serialize_audit_logs
from bookings.models import PropertyBooking
from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from core.paging import paginated_response, query_flag, search_term
from hotels.models import HotelBooking
from listings.models import Property
from support.models import Complaint, ComplaintStatus
from support.serializers import ComplaintSerializer


class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        analytics = compute_analytics()
        pending_verifications = VerificationDocument.objects.filter(
            status=VerificationDocument.Status.PENDING,
        ).order_by('-created_at')[:20]
        open_disputes = Dispute.objects.filter(
            status=DisputeStatus.OPEN,
            is_deleted=False,
        ).order_by('-created_at')[:20]
        in_progress_disputes = Dispute.objects.filter(
            status=DisputeStatus.IN_PROGRESS,
            is_deleted=False,
        ).order_by('-created_at')[:20]
        open_complaints = Complaint.objects.filter(
            is_deleted=False,
        ).exclude(status=ComplaintStatus.RESOLVED).order_by('-created_at')[:20]
        pending_fraud = FraudReport.objects.filter(
            status=FraudReportStatus.PENDING,
            is_deleted=False,
        ).order_by('-created_at')[:20]
        investigating_fraud = FraudReport.objects.filter(
            status=FraudReportStatus.INVESTIGATING,
            is_deleted=False,
        ).order_by('-created_at')[:20]

        return Response(api_success({
            'analytics': analytics,
            'pendingVerifications': VerificationRequestSerializer(
                pending_verifications, many=True, context={'request': request},
            ).data,
            'openDisputes': DisputeSerializer(open_disputes, many=True).data,
            'inProgressDisputes': DisputeSerializer(in_progress_disputes, many=True).data,
            'openComplaints': ComplaintSerializer(open_complaints, many=True).data,
            'pendingFraudReports': FraudReportSerializer(pending_fraud, many=True).data,
            'investigatingFraudReports': FraudReportSerializer(
                investigating_fraud, many=True,
            ).data,
        }))


class AdminUsersView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        qs = (
            User.objects.filter(role=Role.ADMIN)
            .select_related('admin_profile')
            .order_by('phone')
        )
        return Response(api_success(AdminUserSerializer(qs, many=True).data))


class AdminManagedUsersView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        qs = User.objects.exclude(role=Role.ADMIN).order_by('-created_at')

        term = search_term(request)
        if term:
            qs = qs.filter(
                Q(name__icontains=term)
                | Q(email__icontains=term)
                | Q(phone__icontains=term),
            )

        role = query_flag(request, 'role')
        if role in (Role.RENTER, Role.OWNER):
            qs = qs.filter(role=role)

        status_filter = query_flag(request, 'status')
        if status_filter == UserAccountStatus.ACTIVE:
            qs = qs.filter(
                Q(moderation__status=UserAccountStatus.ACTIVE)
                | Q(moderation__isnull=True),
            )
        elif status_filter in (
            UserAccountStatus.SUSPENDED,
            UserAccountStatus.BANNED,
        ):
            qs = qs.filter(moderation__status=status_filter)

        return paginated_response(
            request,
            qs.distinct(),
            serialize_page=lambda page_users: [
                UserManagementSerializer(serialize_managed_user(user)).data
                for user in page_users
            ],
        )


class AdminManagedUserDetailView(APIView):
    """PATCH status and/or verified for a managed (non-admin) user."""

    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist as exc:
            raise NotFoundError('User not found.') from exc
        if user.role == Role.ADMIN:
            raise ForbiddenError('Cannot view admin accounts here.')
        return Response(api_success(
            UserManagementSerializer(serialize_managed_user(user)).data,
        ))

    def patch(self, request, pk):
        serializer = UserModerationPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        admin_role = getattr(request.user, 'admin_role', None)

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist as exc:
            raise NotFoundError('User not found.') from exc

        if user.role == Role.ADMIN:
            raise InvalidError('Cannot moderate admin accounts.')

        moderation = get_or_create_user_moderation(user)
        changes = []

        if 'status' in data:
            new_status = data['status']
            old_status = moderation.status
            needs_ban_perm = (
                new_status == UserAccountStatus.BANNED
                or old_status == UserAccountStatus.BANNED
            )
            required = 'users.ban' if needs_ban_perm else 'users.manage'
            if not admin_has_permission(admin_role, required):
                raise ForbiddenError(f'Missing admin permission: {required}')

            if new_status != old_status:
                moderation.status = new_status
                moderation.save(update_fields=['status', 'updated_at'])
                if new_status == UserAccountStatus.BANNED:
                    user.is_active = False
                else:
                    user.is_active = True
                user.save(update_fields=['is_active', 'updated_at'])
                changes.append({
                    'field': 'accountStatus',
                    'oldValue': old_status,
                    'newValue': new_status,
                })

        if 'verified' in data:
            if not admin_has_permission(admin_role, 'users.manage'):
                raise ForbiddenError('Missing admin permission: users.manage')
            want_verified = bool(data['verified'])
            was_verified = (
                VerificationDocument.objects.filter(
                    user=user,
                    status=VerificationDocument.Status.VERIFIED,
                ).exists()
                or user.is_phone_verified
            )
            if want_verified and not was_verified:
                user.is_phone_verified = True
                user.save(update_fields=['is_phone_verified', 'updated_at'])
                pending = VerificationDocument.objects.filter(
                    user=user,
                    status=VerificationDocument.Status.PENDING,
                )
                now = timezone.now()
                for doc in pending:
                    doc.status = VerificationDocument.Status.VERIFIED
                    doc.reviewed_at = now
                    doc.reviewed_by = request.user
                    doc.save(
                        update_fields=[
                            'status',
                            'reviewed_at',
                            'reviewed_by',
                            'updated_at',
                        ],
                    )
                if not VerificationDocument.objects.filter(user=user).exists():
                    VerificationDocument.objects.create(
                        user=user,
                        verification_type=VerificationDocument.VerificationType.PHONE,
                        document_number=user.phone,
                        file_name='',
                        status=VerificationDocument.Status.VERIFIED,
                        reviewed_at=now,
                        reviewed_by=request.user,
                    )
                changes.append({
                    'field': 'verified',
                    'oldValue': False,
                    'newValue': True,
                })
            elif not want_verified and was_verified:
                VerificationDocument.objects.filter(
                    user=user,
                    status=VerificationDocument.Status.VERIFIED,
                ).update(status=VerificationDocument.Status.PENDING)
                changes.append({
                    'field': 'verified',
                    'oldValue': True,
                    'newValue': False,
                })

        if not changes and 'status' not in data and data.get('verified') is not True:
            raise InvalidError('No changes applied.')

        if changes:
            create_audit_log(
                request.user,
                action='update',
                entity_type='user',
                entity_id=str(user.id),
                entity_name=user.name or user.phone,
                changes=changes,
                rollback_data={
                    'entity_type': 'user',
                    'entity_id': str(user.id),
                    'fields': {c['field']: c['oldValue'] for c in changes},
                },
                can_rollback=True,
                request=request,
            )

        return Response(api_success(
            UserManagementSerializer(serialize_managed_user(user)).data,
        ))


class AdminVerificationsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        qs = VerificationDocument.objects.select_related('user').order_by('-created_at')
        term = search_term(request)
        if term:
            qs = qs.filter(
                Q(user__name__icontains=term)
                | Q(user__phone__icontains=term)
                | Q(document_number__icontains=term),
            )
        status_filter = query_flag(request, 'status')
        # FE uses approved; BE stores verified
        status_map = {
            'pending': VerificationDocument.Status.PENDING,
            'approved': VerificationDocument.Status.VERIFIED,
            'verified': VerificationDocument.Status.VERIFIED,
            'rejected': VerificationDocument.Status.REJECTED,
        }
        if status_filter in status_map:
            qs = qs.filter(status=status_map[status_filter])

        return paginated_response(
            request,
            qs,
            serialize_page=lambda rows: VerificationRequestSerializer(
                rows,
                many=True,
                context={'request': request},
            ).data,
        )


class AdminVerificationDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def patch(self, request, pk):
        serializer = VerificationPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            doc = VerificationDocument.objects.select_related('user').get(pk=pk)
        except VerificationDocument.DoesNotExist as exc:
            raise NotFoundError('Verification request not found.') from exc

        if data['status'] == 'approved':
            doc.status = VerificationDocument.Status.VERIFIED
            doc.rejection_reason = ''
            if doc.verification_type == VerificationDocument.VerificationType.PHONE:
                doc.user.is_phone_verified = True
                doc.user.save(update_fields=['is_phone_verified', 'updated_at'])
        else:
            doc.status = VerificationDocument.Status.REJECTED
            doc.rejection_reason = data.get('rejectionReason') or ''

        doc.reviewed_at = timezone.now()
        doc.reviewed_by = request.user
        doc.save()

        action = 'approve' if data['status'] == 'approved' else 'reject'
        create_audit_log(
            request.user,
            action=action,
            entity_type='verification',
            entity_id=str(doc.id),
            entity_name=f'{doc.verification_type}:{doc.user.phone}',
            metadata={'notes': data.get('notes') or ''},
            request=request,
        )

        return Response(api_success(
            VerificationRequestSerializer(doc, context={'request': request}).data,
        ))


class AdminDisputesView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        qs = Dispute.objects.filter(is_deleted=False).order_by('-created_at')
        term = search_term(request)
        if term:
            qs = qs.filter(
                Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(created_by_name__icontains=term),
            )
        status_filter = query_flag(request, 'status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return paginated_response(
            request,
            qs,
            serialize_page=lambda rows: DisputeSerializer(rows, many=True).data,
        )

    def post(self, request):
        serializer = DisputeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        name = request.user.name or request.user.phone
        dispute = Dispute.objects.create(
            title=data['title'],
            description=data['description'],
            type=data['type'],
            priority=data.get('priority', 'medium'),
            created_by=request.user,
            created_by_name=name,
            related_user_id=data.get('relatedUserId'),
            related_property_id=data.get('relatedPropertyId'),
            related_booking_id=data.get('relatedBookingId'),
            evidence=data.get('evidence') or [],
        )
        return Response(
            api_success(DisputeSerializer(dispute).data),
            status=status.HTTP_201_CREATED,
        )


class AdminDisputeDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def patch(self, request, pk):
        serializer = DisputePatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            dispute = Dispute.objects.get(pk=pk, is_deleted=False)
        except Dispute.DoesNotExist as exc:
            raise NotFoundError('Dispute not found.') from exc

        if 'status' in data:
            dispute.status = data['status']
            if data['status'] in (DisputeStatus.RESOLVED, DisputeStatus.CLOSED):
                dispute.resolved_at = timezone.now()
        if 'assignedTo' in data:
            if data['assignedTo']:
                try:
                    admin = User.objects.get(pk=data['assignedTo'], role=Role.ADMIN)
                except User.DoesNotExist as exc:
                    raise NotFoundError('Assigned admin not found.') from exc
                dispute.assigned_to = admin
                dispute.assigned_to_name = admin.name or admin.phone
                if dispute.status == DisputeStatus.OPEN:
                    dispute.status = DisputeStatus.ASSIGNED
            else:
                dispute.assigned_to = None
                dispute.assigned_to_name = ''
        if 'resolution' in data:
            dispute.resolution = data['resolution']
        if 'priority' in data:
            dispute.priority = data['priority']
        dispute.save()

        return Response(api_success(DisputeSerializer(dispute).data))


class AdminPropertyModerationView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        from listings.models import ListingStatus

        qs = (
            Property.objects.select_related('owner')
            .prefetch_related('image_files')
            .order_by('-created_at')
        )
        term = search_term(request)
        if term:
            qs = qs.filter(
                Q(name__icontains=term)
                | Q(city__icontains=term)
                | Q(area__icontains=term)
                | Q(owner__name__icontains=term)
                | Q(owner__phone__icontains=term),
            )
        prop_type = query_flag(request, 'type') or query_flag(request, 'propertyType')
        if prop_type:
            qs = qs.filter(type=prop_type)

        status_filter = query_flag(request, 'status')
        status_map = {
            'pending': ListingStatus.DRAFT,
            'approved': ListingStatus.PUBLISHED,
            'rejected': ListingStatus.REJECTED,
            'suspended': ListingStatus.PAUSED,
        }
        if status_filter in status_map:
            qs = qs.filter(listing_status=status_map[status_filter])

        return paginated_response(
            request,
            qs,
            serialize_page=lambda rows: [
                PropertyModerationSerializer.from_property(p) for p in rows
            ],
        )


class AdminPropertyModerationDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def patch(self, request, pk):
        from django.utils import timezone
        from listings.models import VerificationStatus

        serializer = PropertyModerationPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            prop = Property.objects.select_related('owner').prefetch_related(
                'image_files',
            ).get(pk=pk)
        except Property.DoesNotExist as exc:
            raise NotFoundError('Property not found.') from exc

        old_status = prop.listing_status
        old_published = prop.published
        old_featured = prop.featured
        old_verified = prop.verified
        changes = []

        if 'status' in data:
            apply_moderation_status(
                prop,
                data['status'],
                rejection_reason=data.get('rejectionReason') or '',
            )
            changes.append({
                'field': 'listingStatus',
                'oldValue': old_status,
                'newValue': prop.listing_status,
            })

        update_fields = []
        if 'featured' in data:
            prop.featured = data['featured']
            update_fields.append('featured')
            changes.append({
                'field': 'featured',
                'oldValue': old_featured,
                'newValue': prop.featured,
            })
        if 'verified' in data:
            prop.verified = data['verified']
            update_fields.append('verified')
            if data['verified']:
                prop.verification_status = VerificationStatus.VERIFIED
                prop.verified_at = timezone.now()
            else:
                prop.verification_status = VerificationStatus.UNVERIFIED
                prop.verified_at = None
            update_fields.extend(['verification_status', 'verified_at'])
            changes.append({
                'field': 'verified',
                'oldValue': old_verified,
                'newValue': prop.verified,
            })
        for flag, attr in (
            ('addressVerified', 'address_verified'),
            ('photosVerified', 'photos_verified'),
            ('rentVerified', 'rent_verified'),
        ):
            if flag in data:
                old = getattr(prop, attr)
                setattr(prop, attr, bool(data[flag]))
                update_fields.append(attr)
                changes.append({
                    'field': flag,
                    'oldValue': old,
                    'newValue': getattr(prop, attr),
                })
        if update_fields:
            update_fields.append('updated_at')
            prop.save(update_fields=list(dict.fromkeys(update_fields)))

        if changes:
            rollback_fields = {
                'listing_status': old_status,
                'published': old_published,
                'featured': old_featured,
                'verified': old_verified,
            }
            create_audit_log(
                request.user,
                action='update',
                entity_type='property',
                entity_id=str(prop.id),
                entity_name=prop.name,
                changes=changes,
                rollback_data={
                    'entity_type': 'property',
                    'entity_id': str(prop.id),
                    'fields': rollback_fields,
                },
                can_rollback=True,
                request=request,
            )

        return Response(api_success(PropertyModerationSerializer.from_property(prop)))


class AdminComplaintsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        qs = Complaint.objects.filter(is_deleted=False).order_by('-created_at')
        term = search_term(request)
        if term:
            qs = qs.filter(
                Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(user_name__icontains=term),
            )
        status_filter = query_flag(request, 'status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return paginated_response(
            request,
            qs,
            serialize_page=lambda rows: ComplaintSerializer(rows, many=True).data,
        )


class AdminFraudReportsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        qs = FraudReport.objects.filter(is_deleted=False).order_by('-created_at')
        term = search_term(request)
        if term:
            qs = qs.filter(
                Q(user_name__icontains=term)
                | Q(description__icontains=term)
                | Q(report_type__icontains=term),
            )
        status_filter = query_flag(request, 'status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return paginated_response(
            request,
            qs,
            serialize_page=lambda rows: FraudReportSerializer(rows, many=True).data,
        )

    def post(self, request):
        serializer = FraudReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = User.objects.get(pk=data['userId'])
        except User.DoesNotExist as exc:
            raise NotFoundError('User not found.') from exc

        report = FraudReport.objects.create(
            user=user,
            user_name=user.name or user.phone,
            report_type=data['reportType'],
            description=data['description'],
            evidence=data.get('evidence') or [],
            priority=data.get('priority', 'medium'),
        )
        return Response(
            api_success(FraudReportSerializer(report).data),
            status=status.HTTP_201_CREATED,
        )


class AdminFraudReportDetailView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def patch(self, request, pk):
        serializer = FraudReportPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            report = FraudReport.objects.get(pk=pk, is_deleted=False)
        except FraudReport.DoesNotExist as exc:
            raise NotFoundError('Fraud report not found.') from exc

        if 'status' in data:
            report.status = data['status']
            if data['status'] == FraudReportStatus.INVESTIGATING:
                report.investigated_by = request.user
        if 'resolution' in data:
            report.resolution = data['resolution']
        if 'priority' in data:
            report.priority = data['priority']
        if 'investigatedBy' in data and data['investigatedBy']:
            try:
                admin = User.objects.get(pk=data['investigatedBy'], role=Role.ADMIN)
            except User.DoesNotExist as exc:
                raise NotFoundError('Investigating admin not found.') from exc
            report.investigated_by = admin
        report.save()

        return Response(api_success(FraudReportSerializer(report).data))


class AdminAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        return Response(api_success(compute_analytics()))


class AdminSettingsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'settings.manage'

    def get(self, request):
        settings_obj = ensure_system_settings()
        return Response(api_success(SystemSettingsSerializer(settings_obj).data))

    def put(self, request):
        serializer = SystemSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        settings_obj = ensure_system_settings()
        validated = serializer.validated_data
        settings_obj.platform_name = validated['platform_name']
        settings_obj.platform_email = validated['platform_email']
        settings_obj.platform_phone = validated['platform_phone']
        settings_obj.commission_rate = validated['commission_rate']
        settings_obj.subscription_plans = validated['subscription_plans']
        settings_obj.feature_flags = validated['feature_flags']
        settings_obj.sms_gateway = validated['sms_gateway']
        settings_obj.email_service = validated['email_service']
        if 'heartbeat' in validated:
            settings_obj.heartbeat = validated['heartbeat']
        if 'push' in validated:
            settings_obj.push = validated['push']
        settings_obj.save()
        return Response(api_success(SystemSettingsSerializer(settings_obj).data))


class AdminActivityLogsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        qs = ActivityLog.objects.all().order_by('-created_at')
        term = search_term(request)
        if term:
            qs = qs.filter(
                Q(user_name__icontains=term)
                | Q(action__icontains=term)
                | Q(resource_type__icontains=term)
                | Q(details__icontains=term),
            )
        return paginated_response(
            request,
            qs,
            serialize_page=lambda rows: ActivityLogSerializer(rows, many=True).data,
        )


class AdminAuditLogsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        qs = filter_audit_logs(
            entity=request.query_params.get('entity'),
            action=request.query_params.get('action'),
            entity_type=request.query_params.get('entityType'),
            user_id=request.query_params.get('userId'),
        )
        term = search_term(request)
        if term:
            qs = qs.filter(
                Q(entity_name__icontains=term)
                | Q(user_name__icontains=term)
                | Q(action__icontains=term)
                | Q(entity_type__icontains=term),
            )
        return paginated_response(
            request,
            qs,
            serialize_page=lambda rows: serialize_audit_logs(rows),
        )


class AdminAuditLogRollbackView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def post(self, request, pk):
        from audit.models import AuditLog

        try:
            log = AuditLog.objects.get(pk=pk)
        except AuditLog.DoesNotExist as exc:
            raise NotFoundError('Audit log not found.') from exc

        log = rollback_audit(log, request.user, request=request)
        from audit.serializers import AuditLogSerializer
        return Response(api_success(AuditLogSerializer(log).data))


class AdminHeartbeatView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'settings.manage'

    def get(self, request):
        from discovery.services.heartbeat import get_heartbeat_config, heartbeat_stats

        return Response(
            api_success(
                {
                    'stats': heartbeat_stats(),
                    'config': get_heartbeat_config(),
                },
            ),
        )

    def post(self, request):
        from discovery.services.heartbeat import run_heartbeat_batch

        send = request.data.get('sendSms')
        send_override = None if send is None else bool(send)
        result = run_heartbeat_batch(force=True, send_sms_override=send_override)
        return Response(api_success(result))


class AdminHeartbeatPingsView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'settings.manage'

    def get(self, request):
        from discovery.models import HeartbeatPing

        qs = HeartbeatPing.objects.select_related('owner').order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        rows = []
        for ping in qs[:100]:
            rows.append(
                {
                    'id': str(ping.id),
                    'token': ping.token,
                    'ownerPhone': ping.owner.phone,
                    'ownerName': ping.owner.name,
                    'targetType': ping.target_type,
                    'targetName': ping.target_name,
                    'city': ping.target_city,
                    'status': ping.status,
                    'dryRun': ping.dry_run,
                    'sentAt': ping.sent_at.isoformat() if ping.sent_at else None,
                    'respondedAt': (
                        ping.responded_at.isoformat() if ping.responded_at else None
                    ),
                    'expiresAt': ping.expires_at.isoformat(),
                    'linkPath': f'/c/{ping.token}',
                    'error': ping.error_message,
                },
            )
        return Response(api_success(rows))


class AdminPushView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    admin_permission = 'settings.manage'

    def get(self, request):
        from messaging.services.push import push_stats

        return Response(api_success(push_stats()))
