"""Admin dashboard analytics and settings helpers."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import Role, User, VerificationDocument
from admin_api.models import Dispute, DisputeStatus, FraudReport, FraudReportStatus, SystemSettings
from bookings.models import PropertyBooking
from hotels.models import HotelBooking
from listings.models import Property, PropertyType
from payments.models import OwnerPayout, PaymentTransaction, PaymentTransactionStatus
from support.models import Complaint, ComplaintStatus


def _pct_growth(current: int, previous: int) -> float:
    if previous <= 0:
        return float(current) if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def default_subscription_plans() -> dict:
    return {
        'free': {
            'maxFlats': 3,
            'features': ['Basic listing', 'Bill management', 'Complaint system'],
        },
        'basic': {
            'price': 500,
            'maxFlats': 10,
            'features': ['All free features', 'Advanced analytics', 'Priority support'],
        },
        'premium': {
            'price': 2000,
            'maxFlats': -1,
            'features': [
                'All basic features',
                'White-label option',
                'API access',
                'Dedicated support',
            ],
        },
    }


def default_feature_flags() -> dict:
    return {
        'hotelModule': True,
        'paymentGateway': True,
        'smsNotifications': True,
        'emailNotifications': True,
        'aiRecommendations': False,
    }


def ensure_system_settings() -> SystemSettings:
    commission_pct = round(float(getattr(settings, 'COMMISSION_RATE', 0.05)) * 100, 2)
    obj = SystemSettings.load()
    if not obj.subscription_plans:
        obj.platform_name = obj.platform_name or 'SmartBasa'
        obj.commission_rate = obj.commission_rate or commission_pct or 5.0
        obj.subscription_plans = default_subscription_plans()
        obj.feature_flags = obj.feature_flags or default_feature_flags()
        obj.sms_gateway = obj.sms_gateway or {
            'provider': 'console',
            'enabled': False,
        }
        obj.email_service = obj.email_service or {
            'provider': 'stub',
            'enabled': False,
        }
        obj.save()
    updates = []
    if not obj.heartbeat:
        from discovery.services.heartbeat import default_heartbeat_config

        obj.heartbeat = default_heartbeat_config()
        updates.append('heartbeat')
    if not obj.push:
        from messaging.services.push import default_push_config

        obj.push = default_push_config()
        updates.append('push')
    if updates:
        obj.save(update_fields=updates)
    return obj


def _property_type_bucket(prop_type: str) -> str:
    if prop_type == PropertyType.MESS:
        return 'mess'
    if prop_type == PropertyType.HOTEL:
        return 'hotel'
    return 'apartment'


def compute_analytics() -> dict:
    now = timezone.now()
    last_30 = now - timedelta(days=30)
    prev_30_start = now - timedelta(days=60)

    total_users = User.objects.count()
    users_by_role = {
        'renters': User.objects.filter(role=Role.RENTER).count(),
        'owners': User.objects.filter(role=Role.OWNER).count(),
        'admins': User.objects.filter(role=Role.ADMIN).count(),
    }

    properties = Property.objects.all()
    total_properties = properties.count()
    by_type = {'mess': 0, 'apartment': 0, 'hotel': 0}
    for row in properties.values('type').annotate(c=Count('id')):
        bucket = _property_type_bucket(row['type'])
        by_type[bucket] = by_type.get(bucket, 0) + row['c']

    prop_bookings = PropertyBooking.objects.filter(is_deleted=False).count()
    hotel_bookings = HotelBooking.objects.filter(is_deleted=False).count()
    total_bookings = prop_bookings + hotel_bookings

    txn_revenue = PaymentTransaction.objects.filter(
        status=PaymentTransactionStatus.COMPLETED,
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    payout_revenue = OwnerPayout.objects.filter(
        status='paid',
    ).aggregate(total=Coalesce(Sum('gross_amount'), Decimal('0')))['total']
    total_revenue = float(txn_revenue or payout_revenue or 0)

    pending_verifications = VerificationDocument.objects.filter(
        status=VerificationDocument.Status.PENDING,
    ).count()
    open_disputes = Dispute.objects.filter(
        status__in=[DisputeStatus.OPEN, DisputeStatus.ASSIGNED],
        is_deleted=False,
    ).count()
    open_complaints = Complaint.objects.filter(
        is_deleted=False,
    ).exclude(status=ComplaintStatus.RESOLVED).count()

    users_last_30 = User.objects.filter(created_at__gte=last_30).count()
    users_prev_30 = User.objects.filter(
        created_at__gte=prev_30_start,
        created_at__lt=last_30,
    ).count()
    props_last_30 = Property.objects.filter(created_at__gte=last_30).count()
    props_prev_30 = Property.objects.filter(
        created_at__gte=prev_30_start,
        created_at__lt=last_30,
    ).count()
    bookings_last_30 = (
        PropertyBooking.objects.filter(created_at__gte=last_30, is_deleted=False).count()
        + HotelBooking.objects.filter(created_at__gte=last_30, is_deleted=False).count()
    )
    bookings_prev_30 = (
        PropertyBooking.objects.filter(
            created_at__gte=prev_30_start,
            created_at__lt=last_30,
            is_deleted=False,
        ).count()
        + HotelBooking.objects.filter(
            created_at__gte=prev_30_start,
            created_at__lt=last_30,
            is_deleted=False,
        ).count()
    )
    rev_last_30 = PaymentTransaction.objects.filter(
        status=PaymentTransactionStatus.COMPLETED,
        completed_at__gte=last_30,
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    rev_prev_30 = PaymentTransaction.objects.filter(
        status=PaymentTransactionStatus.COMPLETED,
        completed_at__gte=prev_30_start,
        completed_at__lt=last_30,
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']

    city_rows = (
        Property.objects.values('city')
        .annotate(properties=Count('id'))
        .order_by('-properties')[:10]
    )
    city_wise = [
        {
            'city': row['city'] or 'Unknown',
            'properties': row['properties'],
            'bookings': 0,
            'revenue': 0,
        }
        for row in city_rows
    ]

    return {
        'totalUsers': total_users,
        'usersByRole': users_by_role,
        'totalProperties': total_properties,
        'propertiesByType': by_type,
        'totalBookings': total_bookings,
        'totalRevenue': total_revenue,
        'pendingVerifications': pending_verifications,
        'openDisputes': open_disputes,
        'openComplaints': open_complaints,
        'growthMetrics': {
            'usersGrowth': _pct_growth(users_last_30, users_prev_30),
            'propertiesGrowth': _pct_growth(props_last_30, props_prev_30),
            'bookingsGrowth': _pct_growth(bookings_last_30, bookings_prev_30),
            'revenueGrowth': _pct_growth(int(rev_last_30 or 0), int(rev_prev_30 or 0)),
        },
        'cityWiseStats': city_wise,
    }


def map_listing_to_moderation_status(prop: Property) -> str:
    from listings.models import ListingStatus

    if prop.listing_status == ListingStatus.REJECTED:
        return 'rejected'
    if prop.listing_status == ListingStatus.PAUSED:
        return 'suspended'
    if prop.listing_status == ListingStatus.PUBLISHED and prop.published:
        return 'approved'
    return 'pending'


def apply_moderation_status(prop: Property, status: str, *, rejection_reason: str = '') -> Property:
    from listings.models import ListingStatus

    if status == 'approved':
        prop.listing_status = ListingStatus.PUBLISHED
        prop.published = True
    elif status == 'rejected':
        prop.listing_status = ListingStatus.REJECTED
        prop.published = False
    elif status == 'suspended':
        prop.listing_status = ListingStatus.PAUSED
        prop.published = False
    elif status == 'pending':
        prop.listing_status = ListingStatus.DRAFT
        prop.published = False
    prop.save()
    return prop


def get_or_create_user_moderation(user: User):
    from admin_api.models import UserAccountStatus, UserModeration

    moderation, _ = UserModeration.objects.get_or_create(
        user=user,
        defaults={'status': UserAccountStatus.ACTIVE},
    )
    return moderation


def serialize_managed_user(user) -> dict:
    """Full UserManagement payload for list + PATCH responses."""
    from bookings.models import PropertyBooking
    from hotels.models import HotelBooking
    from listings.models import Property
    from support.models import Complaint

    moderation = get_or_create_user_moderation(user)
    verified = VerificationDocument.objects.filter(
        user=user,
        status=VerificationDocument.Status.VERIFIED,
    ).exists() or user.is_phone_verified
    total_properties = Property.objects.filter(owner=user).count()
    total_bookings = (
        PropertyBooking.objects.filter(renter=user, is_deleted=False).count()
        + HotelBooking.objects.filter(user=user, is_deleted=False).count()
    )
    total_complaints = Complaint.objects.filter(user=user, is_deleted=False).count()
    activity_score = min(100, (total_bookings * 10) + (total_properties * 5))
    return {
        'id': user.id,
        'name': user.name or user.phone,
        'email': user.email or '',
        'phone': user.phone,
        'role': user.role,
        'status': moderation.status,
        'verified': verified,
        'createdAt': user.created_at.isoformat().replace('+00:00', 'Z'),
        'lastLogin': (
            user.last_login.isoformat().replace('+00:00', 'Z')
            if user.last_login
            else None
        ),
        'totalProperties': total_properties or None,
        'totalBookings': total_bookings or None,
        'totalComplaints': total_complaints or None,
        'activityScore': activity_score,
    }


def map_verification_status(status: str) -> str:
    if status == VerificationDocument.Status.VERIFIED:
        return 'approved'
    if status == VerificationDocument.Status.REJECTED:
        return 'rejected'
    return 'pending'
