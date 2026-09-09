from rest_framework import serializers

from core.services.media import media_storage
from discovery.services.freshness import freshness_dict
from hotels.models import (
    DEFAULT_CANCELLATION,
    DEFAULT_PRICING_RULES,
    Hotel,
    HotelBooking,
    HotelReview,
    Room,
    RoomPrice,
)


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


class HotelSerializer(serializers.ModelSerializer):
    ownerId = serializers.UUIDField(source='owner_id', read_only=True)
    starRating = serializers.IntegerField(source='star_rating', allow_null=True, required=False)
    ownerName = serializers.CharField(source='owner_name', read_only=True)
    ownerPhone = serializers.CharField(source='owner_phone', read_only=True)
    ownerWhatsapp = serializers.SerializerMethodField()
    ownerEmail = serializers.CharField(source='owner_email', read_only=True, allow_blank=True)
    checkInTime = serializers.CharField(source='check_in_time')
    checkOutTime = serializers.CharField(source='check_out_time')
    minimumStay = serializers.IntegerField(source='minimum_stay')
    licenseNumber = serializers.CharField(
        source='license_number',
        required=False,
        allow_blank=True,
    )
    licenseDocument = serializers.CharField(
        source='license_document',
        required=False,
        allow_blank=True,
    )
    licenseDocumentUrl = serializers.SerializerMethodField()
    averageRating = serializers.FloatField(source='average_rating', read_only=True)
    totalReviews = serializers.IntegerField(source='total_reviews', read_only=True)
    totalRooms = serializers.IntegerField(source='total_rooms', read_only=True)
    availableRooms = serializers.IntegerField(source='available_rooms', read_only=True)
    cancellationPolicy = serializers.JSONField(source='cancellation_policy', required=False)
    pricingRules = serializers.JSONField(source='pricing_rules', required=False)
    advancePaymentPercent = serializers.IntegerField(
        source='advance_payment_percent',
        required=False,
    )
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    featuredUntil = serializers.DateTimeField(
        source='featured_until',
        allow_null=True,
        read_only=True,
    )
    lastConfirmedAt = serializers.DateTimeField(
        source='last_confirmed_at',
        allow_null=True,
        read_only=True,
    )
    confirmedHoursAgo = serializers.SerializerMethodField()
    stale = serializers.SerializerMethodField()

    class Meta:
        model = Hotel
        fields = (
            'id',
            'name',
            'type',
            'starRating',
            'ownerId',
            'ownerName',
            'ownerPhone',
            'ownerWhatsapp',
            'ownerEmail',
            'address',
            'area',
            'city',
            'latitude',
            'longitude',
            'images',
            'description',
            'amenities',
            'checkInTime',
            'checkOutTime',
            'minimumStay',
            'licenseNumber',
            'licenseDocument',
            'licenseDocumentUrl',
            'verified',
            'featured',
            'averageRating',
            'totalReviews',
            'totalRooms',
            'availableRooms',
            'featuredUntil',
            'lastConfirmedAt',
            'confirmedHoursAgo',
            'stale',
            'cancellationPolicy',
            'pricingRules',
            'advancePaymentPercent',
            'createdAt',
            'updatedAt',
        )
        read_only_fields = (
            'id',
            'ownerId',
            'ownerName',
            'ownerPhone',
            'ownerWhatsapp',
            'ownerEmail',
            'verified',
            'featured',
            'averageRating',
            'totalReviews',
            'totalRooms',
            'availableRooms',
            'createdAt',
            'updatedAt',
        )

    def get_ownerWhatsapp(self, obj) -> str:
        """Live from the account so a later profile edit is picked up."""
        return getattr(obj.owner, 'whatsapp_number', '') or ''

    def get_licenseDocumentUrl(self, obj) -> str:
        """Signed link for a privately stored license, else the stored value."""
        if obj.license_document_key:
            return media_storage.signed_url(
                obj.license_document_key,
                request=self.context.get('request'),
            )
        return obj.license_document if obj.license_document.startswith('http') else ''

    def get_confirmedHoursAgo(self, obj):
        return freshness_dict(obj)['confirmedHoursAgo']

    def get_stale(self, obj):
        return freshness_dict(obj)['stale']


class HotelRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2)
    type = serializers.ChoiceField(choices=['hotel', 'guest-house', 'resort'])
    starRating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    address = serializers.CharField()
    area = serializers.CharField()
    city = serializers.CharField()
    description = serializers.CharField(min_length=20)
    amenities = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    checkInTime = serializers.CharField()
    checkOutTime = serializers.CharField()
    minimumStay = serializers.IntegerField(min_value=1)
    licenseNumber = serializers.CharField(required=False, allow_blank=True, default='')
    licenseDocumentName = serializers.CharField(required=False, allow_blank=True, default='')
    licenseDocumentKey = serializers.CharField(required=False, allow_blank=True, default='')
    imageUrl = serializers.URLField(required=False, allow_blank=True)
    weekendMultiplier = serializers.FloatField(min_value=1)
    serviceChargePercent = serializers.FloatField(min_value=0)
    vatPercent = serializers.FloatField(min_value=0)
    freeCancellationHours = serializers.IntegerField(min_value=0)
    partialRefundPercent = serializers.IntegerField(min_value=0, max_value=100)

    def create_hotel(self, owner):
        data = self.validated_data
        summary = (
            f'Free cancellation up to {data["freeCancellationHours"]} hours before check-in. '
            f'{data["partialRefundPercent"]}% refund between free window and 24 hours. '
            'No refund within 24 hours.'
        )
        images = [data['imageUrl']] if data.get('imageUrl') else []
        return Hotel.objects.create(
            owner=owner,
            name=data['name'].strip(),
            type=data['type'],
            star_rating=data.get('starRating'),
            address=data['address'].strip(),
            area=data['area'].strip(),
            city=data['city'].strip(),
            description=data['description'].strip(),
            amenities=data.get('amenities') or [],
            check_in_time=data['checkInTime'],
            check_out_time=data['checkOutTime'],
            minimum_stay=data['minimumStay'],
            license_number=data.get('licenseNumber') or '',
            license_document=data.get('licenseDocumentName') or '',
            license_document_key=media_storage.ensure_key(
                data.get('licenseDocumentKey') or '',
                'document',
            ),
            images=images,
            cancellation_policy={
                **DEFAULT_CANCELLATION,
                'freeCancellationHours': data['freeCancellationHours'],
                'partialRefundPercent': data['partialRefundPercent'],
                'summary': summary,
            },
            pricing_rules={
                **DEFAULT_PRICING_RULES,
                'weekendMultiplier': data['weekendMultiplier'],
                'serviceChargePercent': data['serviceChargePercent'],
                'vatPercent': data['vatPercent'],
            },
        )


class HotelPricingUpdateSerializer(serializers.Serializer):
    pricingRules = serializers.JSONField(required=False)
    cancellationPolicy = serializers.JSONField(required=False)
    advancePaymentPercent = serializers.IntegerField(min_value=0, max_value=100, required=False)


class RoomSerializer(serializers.ModelSerializer):
    hotelId = serializers.UUIDField(source='hotel_id', read_only=True)
    roomNumber = serializers.CharField(source='room_number')
    basePrice = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Room
        fields = (
            'id',
            'hotelId',
            'roomNumber',
            'type',
            'floor',
            'capacity',
            'basePrice',
            'amenities',
            'images',
            'description',
            'available',
            'createdAt',
            'updatedAt',
        )
        read_only_fields = ('id', 'hotelId', 'createdAt', 'updatedAt')

    def get_basePrice(self, obj):
        return _money(obj.base_price)


class RoomWriteSerializer(serializers.ModelSerializer):
    roomNumber = serializers.CharField(source='room_number')
    basePrice = serializers.DecimalField(source='base_price', max_digits=12, decimal_places=2)
    amenities = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    images = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        default=list,
    )
    description = serializers.CharField(required=False, allow_blank=True, default='')
    available = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = Room
        fields = (
            'roomNumber',
            'type',
            'floor',
            'capacity',
            'basePrice',
            'amenities',
            'images',
            'description',
            'available',
        )


class RoomPricingSerializer(serializers.Serializer):
    roomId = serializers.UUIDField()
    date = serializers.DateField()
    price = serializers.FloatField()
    isWeekend = serializers.BooleanField()
    isSpecialOffer = serializers.BooleanField()
    offerPrice = serializers.FloatField(required=False, allow_null=True)


class HotelBookingSerializer(serializers.ModelSerializer):
    hotelId = serializers.UUIDField(source='hotel_id', read_only=True)
    roomId = serializers.UUIDField(source='room_id', read_only=True)
    userId = serializers.UUIDField(source='user_id', read_only=True)
    guestName = serializers.CharField(source='guest_name', read_only=True)
    guestPhone = serializers.CharField(source='guest_phone', read_only=True)
    guestWhatsapp = serializers.SerializerMethodField()
    guestEmail = serializers.CharField(source='guest_email', read_only=True, allow_blank=True)
    checkIn = serializers.DateField(source='check_in', read_only=True)
    checkOut = serializers.DateField(source='check_out', read_only=True)
    checkInTime = serializers.CharField(source='check_in_time', read_only=True)
    checkOutTime = serializers.CharField(source='check_out_time', read_only=True)
    paymentStatus = serializers.CharField(source='payment_status', read_only=True)
    totalAmount = serializers.SerializerMethodField()
    advanceAmount = serializers.SerializerMethodField()
    remainingAmount = serializers.SerializerMethodField()
    paymentMethod = serializers.CharField(source='payment_method', read_only=True, allow_blank=True)
    transactionId = serializers.CharField(source='transaction_id', read_only=True, allow_blank=True)
    specialRequests = serializers.CharField(source='special_requests', read_only=True)
    feeBreakdown = serializers.JSONField(source='fee_breakdown', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = HotelBooking
        fields = (
            'id',
            'hotelId',
            'roomId',
            'userId',
            'guestName',
            'guestPhone',
            'guestWhatsapp',
            'guestEmail',
            'checkIn',
            'checkOut',
            'checkInTime',
            'checkOutTime',
            'guests',
            'status',
            'paymentStatus',
            'totalAmount',
            'advanceAmount',
            'remainingAmount',
            'paymentMethod',
            'transactionId',
            'specialRequests',
            'feeBreakdown',
            'createdAt',
            'updatedAt',
        )
        read_only_fields = fields

    def get_guestWhatsapp(self, obj) -> str:
        return getattr(obj.user, 'whatsapp_number', '') or ''

    def get_totalAmount(self, obj):
        return _money(obj.total_amount)

    def get_advanceAmount(self, obj):
        return _money(obj.advance_amount)

    def get_remainingAmount(self, obj):
        return _money(obj.remaining_amount)


class HotelBookingCreateSerializer(serializers.Serializer):
    roomId = serializers.UUIDField()
    guestName = serializers.CharField()
    guestPhone = serializers.CharField()
    guestEmail = serializers.EmailField(required=False, allow_blank=True, default='')
    checkIn = serializers.DateField()
    checkOut = serializers.DateField()
    guests = serializers.IntegerField(min_value=1)
    paymentMethod = serializers.ChoiceField(
        choices=['bkash', 'nagad', 'rocket', 'card', 'cash'],
        required=False,
        allow_blank=True,
    )
    transactionId = serializers.CharField(required=False, allow_blank=True, default='')
    specialRequests = serializers.CharField(required=False, allow_blank=True, default='')
    paymentStatus = serializers.ChoiceField(
        choices=['pending', 'paid', 'partial'],
        required=False,
        default='pending',
    )
    advanceAmount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        if attrs['checkOut'] <= attrs['checkIn']:
            raise serializers.ValidationError({'checkOut': 'Check-out must be after check-in.'})
        return attrs


class HotelBookingCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default='')


class HotelReviewSerializer(serializers.ModelSerializer):
    hotelId = serializers.UUIDField(source='hotel_id', read_only=True)
    bookingId = serializers.UUIDField(source='booking_id', read_only=True, allow_null=True)
    userId = serializers.UUIDField(source='user_id', read_only=True)
    userName = serializers.CharField(source='user_name', read_only=True)
    userAvatar = serializers.CharField(source='user_avatar', read_only=True, allow_blank=True)
    ownerResponse = serializers.CharField(source='owner_response', read_only=True)
    ownerResponseDate = serializers.DateTimeField(
        source='owner_response_date',
        read_only=True,
        allow_null=True,
    )
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = HotelReview
        fields = (
            'id',
            'hotelId',
            'bookingId',
            'userId',
            'userName',
            'userAvatar',
            'rating',
            'comment',
            'images',
            'createdAt',
            'ownerResponse',
            'ownerResponseDate',
        )
        read_only_fields = fields


class HotelReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(min_length=10)
    bookingId = serializers.UUIDField(required=False, allow_null=True)
    images = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        default=list,
    )
