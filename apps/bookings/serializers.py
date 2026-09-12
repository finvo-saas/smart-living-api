from datetime import date, datetime

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import serializers

from bookings.models import PropertyBooking


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


class PropertyBookingSerializer(serializers.ModelSerializer):
    propertyId = serializers.UUIDField(source='property_id', read_only=True)
    propertyName = serializers.CharField(source='property_name', read_only=True)
    propertyType = serializers.CharField(source='property_type', read_only=True)
    propertyAddress = serializers.CharField(source='property_address', read_only=True)
    propertyImage = serializers.CharField(
        source='property_image',
        read_only=True,
        allow_blank=True,
    )
    flatId = serializers.UUIDField(source='flat_id', read_only=True, allow_null=True)
    flatNumber = serializers.SerializerMethodField()
    renterId = serializers.UUIDField(source='renter_id', read_only=True)
    renterName = serializers.CharField(source='renter_name', read_only=True)
    renterPhone = serializers.CharField(source='renter_phone', read_only=True)
    renterWhatsapp = serializers.SerializerMethodField()
    renterEmail = serializers.CharField(
        source='renter_email',
        read_only=True,
        allow_blank=True,
    )
    ownerId = serializers.UUIDField(source='owner_id', read_only=True)
    ownerName = serializers.CharField(source='owner_name', read_only=True)
    ownerPhone = serializers.CharField(source='owner_phone', read_only=True)
    ownerWhatsapp = serializers.SerializerMethodField()
    bookingMode = serializers.CharField(source='booking_mode', read_only=True)
    moveInDate = serializers.DateField(source='move_in_date', read_only=True, allow_null=True)
    moveOutDate = serializers.DateField(source='move_out_date', read_only=True, allow_null=True)
    totalAmount = serializers.SerializerMethodField()
    rent = serializers.SerializerMethodField()
    deposit = serializers.SerializerMethodField()
    specialRequests = serializers.CharField(source='special_requests', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    approvedAt = serializers.DateTimeField(source='approved_at', read_only=True, allow_null=True)
    rejectedAt = serializers.DateTimeField(source='rejected_at', read_only=True, allow_null=True)
    cancelledAt = serializers.DateTimeField(source='cancelled_at', read_only=True, allow_null=True)
    completedAt = serializers.DateTimeField(source='completed_at', read_only=True, allow_null=True)
    rejectionReason = serializers.CharField(source='rejection_reason', read_only=True)
    cancellationReason = serializers.CharField(source='cancellation_reason', read_only=True)

    class Meta:
        model = PropertyBooking
        fields = (
            'id',
            'propertyId',
            'propertyName',
            'propertyType',
            'propertyAddress',
            'propertyImage',
            'flatId',
            'flatNumber',
            'renterId',
            'renterName',
            'renterPhone',
            'renterWhatsapp',
            'renterEmail',
            'ownerId',
            'ownerName',
            'ownerPhone',
            'ownerWhatsapp',
            'status',
            'bookingMode',
            'moveInDate',
            'moveOutDate',
            'duration',
            'rent',
            'deposit',
            'totalAmount',
            'message',
            'specialRequests',
            'createdAt',
            'updatedAt',
            'approvedAt',
            'rejectedAt',
            'cancelledAt',
            'rejectionReason',
            'cancellationReason',
            'completedAt',
        )
        read_only_fields = fields

    def get_flatNumber(self, obj) -> str | None:
        if obj.flat_id and getattr(obj, 'flat', None):
            return obj.flat.flat_number
        return None

    def get_renterWhatsapp(self, obj) -> str:
        return getattr(obj.renter, 'whatsapp_number', '') or ''

    def get_ownerWhatsapp(self, obj) -> str:
        return getattr(obj.owner, 'whatsapp_number', '') or ''

    def get_rent(self, obj):
        return _money(obj.rent)

    def get_deposit(self, obj):
        return _money(obj.deposit)

    def get_totalAmount(self, obj):
        return _money(obj.total_amount)


def _coerce_date(value):
    """Accept YYYY-MM-DD and ISO timestamps. Calendar dates stay on the picked day."""
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    parsed = parse_date(text)
    if parsed is not None:
        return parsed
    parsed_dt = parse_datetime(text)
    if parsed_dt is not None:
        if timezone.is_aware(parsed_dt):
            parsed_dt = timezone.localtime(parsed_dt)
        return parsed_dt.date()
    raise serializers.ValidationError('Use a date like YYYY-MM-DD.')


class PropertyBookingCreateSerializer(serializers.Serializer):
    propertyId = serializers.UUIDField()
    moveInDate = serializers.CharField()
    moveOutDate = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    duration = serializers.IntegerField(min_value=1, required=False, default=1)
    message = serializers.CharField(required=False, allow_blank=True, default='')
    specialRequests = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        try:
            move_in = _coerce_date(attrs['moveInDate'])
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({'moveInDate': exc.detail}) from exc
        if move_in is None:
            raise serializers.ValidationError({'moveInDate': 'Move-in date is required.'})
        try:
            move_out = _coerce_date(attrs.get('moveOutDate'))
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({'moveOutDate': exc.detail}) from exc
        if move_out and move_out <= move_in:
            raise serializers.ValidationError(
                {'moveOutDate': 'Move-out must be after move-in.'},
            )
        return {
            'property_id': attrs['propertyId'],
            'move_in_date': move_in,
            'move_out_date': move_out,
            'duration': attrs.get('duration') or 1,
            'message': attrs.get('message') or '',
            'special_requests': attrs.get('specialRequests') or '',
        }


class PropertyBookingStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['pending', 'approved', 'rejected', 'cancelled', 'completed'],
    )
    reason = serializers.CharField(required=False, allow_blank=True, default='')
    flatId = serializers.UUIDField(required=False, allow_null=True)
