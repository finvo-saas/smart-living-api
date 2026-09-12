from rest_framework import serializers

from accounts.fields import WhatsAppNumberField
from discovery.services.freshness import freshness_dict
from mess.models import (
    AttendanceRecord,
    DailyMenu,
    MealPreference,
    MealTiming,
    Mess,
    MessExpense,
    MessNotice,
    MessNoticeAck,
    MessRule,
    MessStudent,
    OccupantType,
    RuleAcceptance,
    RuleViolation,
    Seat,
    SMSGroup,
    SMSMessage,
    SMSTemplate,
    WeeklySchedule,
)


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _bill(value):
    if value is None:
        return None
    return _money(value)


def _date_str(dt) -> str:
    if dt is None:
        return ''
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()
    return str(dt)


def _dt_str(dt) -> str:
    if dt is None:
        return ''
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()
    return str(dt)


class MessSerializer(serializers.ModelSerializer):
    totalSeats = serializers.IntegerField(source='total_seats', read_only=True)
    availableSeats = serializers.IntegerField(source='available_seats', read_only=True)
    monthlyFee = serializers.FloatField(source='monthly_fee')
    electricityBill = serializers.SerializerMethodField()
    gasBill = serializers.SerializerMethodField()
    internetBill = serializers.SerializerMethodField()
    waterBill = serializers.SerializerMethodField()
    ownerName = serializers.CharField(source='owner_name', read_only=True)
    ownerPhone = serializers.CharField(source='owner_phone', read_only=True)
    ownerWhatsapp = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    listingId = serializers.UUIDField(source='listing_id', read_only=True, allow_null=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    featured = serializers.BooleanField(read_only=True)
    lastConfirmedAt = serializers.DateTimeField(
        source='last_confirmed_at',
        allow_null=True,
        read_only=True,
    )
    confirmedHoursAgo = serializers.SerializerMethodField()
    stale = serializers.SerializerMethodField()
    liveStatus = serializers.SerializerMethodField()
    mealSystem = serializers.SerializerMethodField()
    utilities = serializers.SerializerMethodField()
    bookUrl = serializers.SerializerMethodField()
    livingCost = serializers.SerializerMethodField()

    class Meta:
        model = Mess
        fields = (
            'id',
            'name',
            'address',
            'city',
            'totalSeats',
            'availableSeats',
            'monthlyFee',
            'electricityBill',
            'gasBill',
            'internetBill',
            'waterBill',
            'gender',
            'facilities',
            'images',
            'description',
            'ownerName',
            'ownerPhone',
            'ownerWhatsapp',
            'createdAt',
            'listingId',
            'latitude',
            'longitude',
            'featured',
            'lastConfirmedAt',
            'confirmedHoursAgo',
            'stale',
            'liveStatus',
            'mealSystem',
            'utilities',
            'bookUrl',
            'livingCost',
        )

    def get_ownerWhatsapp(self, obj) -> str:
        """Live from the account so a later profile edit is picked up."""
        return getattr(obj.owner, 'whatsapp_number', '') or ''

    def get_electricityBill(self, obj):
        return _bill(obj.electricity_bill)

    def get_gasBill(self, obj):
        return _bill(obj.gas_bill)

    def get_internetBill(self, obj):
        return _bill(obj.internet_bill)

    def get_waterBill(self, obj):
        return _bill(obj.water_bill)

    def get_latitude(self, obj):
        listing = getattr(obj, 'listing', None)
        if listing is not None and listing.latitude is not None:
            return float(listing.latitude)
        return None

    def get_longitude(self, obj):
        listing = getattr(obj, 'listing', None)
        if listing is not None and listing.longitude is not None:
            return float(listing.longitude)
        return None

    def get_confirmedHoursAgo(self, obj):
        return freshness_dict(obj)['confirmedHoursAgo']

    def get_stale(self, obj):
        return freshness_dict(obj)['stale']

    def get_liveStatus(self, obj):
        from mess.services.live_status import serialize_live_status

        return serialize_live_status(obj)

    def get_mealSystem(self, obj):
        from mess.services.meal_public import meal_system_summary

        return meal_system_summary(obj)

    def get_utilities(self, obj):
        from mess.services.reliability import reliability_bundle

        return reliability_bundle(obj)

    def get_bookUrl(self, obj):
        if obj.listing_id:
            return f'/listings/{obj.listing_id}'
        return None

    def get_livingCost(self, obj):
        from listings.services.living_cost import (
            estimate_living_cost,
            living_cost_for_property,
        )

        listing = getattr(obj, 'listing', None)
        if listing is not None:
            return living_cost_for_property(listing)
        meal = obj.meal_monthly_charge
        return estimate_living_cost(
            rent=float(obj.monthly_fee or 0),
            property_type='mess',
            meal_included=meal is not None,
            meal_cost=float(meal) if meal is not None else None,
            electricity=float(obj.electricity_bill) if obj.electricity_bill is not None else None,
            gas=float(obj.gas_bill) if obj.gas_bill is not None else None,
            internet=float(obj.internet_bill) if obj.internet_bill is not None else None,
            water=float(obj.water_bill) if obj.water_bill is not None else None,
            seats=int(obj.total_seats or 0),
        )


class MessCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=80)
    monthlyFee = serializers.DecimalField(max_digits=12, decimal_places=2, source='monthly_fee')
    electricityBill = serializers.DecimalField(
        max_digits=12, decimal_places=2, source='electricity_bill', required=False, allow_null=True,
    )
    gasBill = serializers.DecimalField(
        max_digits=12, decimal_places=2, source='gas_bill', required=False, allow_null=True,
    )
    internetBill = serializers.DecimalField(
        max_digits=12, decimal_places=2, source='internet_bill', required=False, allow_null=True,
    )
    waterBill = serializers.DecimalField(
        max_digits=12, decimal_places=2, source='water_bill', required=False, allow_null=True,
    )
    gender = serializers.ChoiceField(choices=['male', 'female', 'mixed'])
    facilities = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    images = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    totalSeats = serializers.IntegerField(source='total_seats', required=False, default=0)
    listingId = serializers.UUIDField(required=False, allow_null=True)
    publishListing = serializers.BooleanField(required=False, default=True)

    def create_mess(self, owner):
        data = dict(self.validated_data)
        listing_id = data.pop('listingId', None)
        publish_listing = data.pop('publishListing', True)
        target_seats = int(data.pop('total_seats', 0) or 0)
        # Counts are derived from Seat rows after capacity sync.
        data['total_seats'] = 0
        data['available_seats'] = 0
        mess = Mess.objects.create(owner=owner, **data)
        from mess.services.seats_capacity import ensure_seat_capacity

        if target_seats > 0:
            ensure_seat_capacity(mess, target_seats)
        from listings.services.inventory import (
            attach_listing_to_mess,
            ensure_listing_for_mess,
        )

        if listing_id:
            attach_listing_to_mess(mess, listing_id)
        elif publish_listing:
            listing = ensure_listing_for_mess(mess)
            try:
                from discovery.services.geocode import ensure_property_coordinates

                ensure_property_coordinates(listing)
            except Exception:
                pass
        return mess


class MessUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    address = serializers.CharField(max_length=255, required=False)
    city = serializers.CharField(max_length=80, required=False)
    monthlyFee = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        source='monthly_fee',
        required=False,
    )
    electricityBill = serializers.DecimalField(
        max_digits=12, decimal_places=2, source='electricity_bill', required=False, allow_null=True,
    )
    gasBill = serializers.DecimalField(
        max_digits=12, decimal_places=2, source='gas_bill', required=False, allow_null=True,
    )
    internetBill = serializers.DecimalField(
        max_digits=12, decimal_places=2, source='internet_bill', required=False, allow_null=True,
    )
    waterBill = serializers.DecimalField(
        max_digits=12, decimal_places=2, source='water_bill', required=False, allow_null=True,
    )
    gender = serializers.ChoiceField(
        choices=['male', 'female', 'mixed'],
        required=False,
    )
    facilities = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    images = serializers.ListField(child=serializers.CharField(), required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    totalSeats = serializers.IntegerField(source='total_seats', required=False, min_value=0)
    publishListing = serializers.BooleanField(required=False)

    def update_mess(self, mess):
        data = dict(self.validated_data)
        publish_listing = data.pop('publishListing', None)
        target_seats = data.pop('total_seats', None)
        for field, value in data.items():
            setattr(mess, field, value)
        mess.save()
        if target_seats is not None:
            from mess.services.seats_capacity import ensure_seat_capacity

            ensure_seat_capacity(mess, target_seats)
        from listings.services.inventory import (
            ensure_listing_for_mess,
            sync_mess_listing,
        )

        address_changed = 'address' in data or 'city' in data
        if publish_listing is True:
            listing = ensure_listing_for_mess(mess)
        else:
            listing = sync_mess_listing(mess)
        if listing is not None:
            _refresh_listing_pin(listing, force=address_changed)
        mess.refresh_from_db()
        return mess


def _refresh_listing_pin(listing, *, force: bool) -> None:
    """Fill a missing pin, or move it when the owner changed the address."""
    try:
        from discovery.services.geocode import (
            ensure_property_coordinates,
            refresh_property_coordinates,
        )
        from listings.services.poi_enrich import refresh_nearby_facilities

        moved = (
            refresh_property_coordinates(listing)
            if force
            else ensure_property_coordinates(listing)
        )
        if moved:
            listing.refresh_from_db()
            if listing.latitude is not None and listing.longitude is not None:
                refresh_nearby_facilities(listing)
    except Exception:
        return


class StudentSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    messName = serializers.CharField(source='mess.name', read_only=True)
    userId = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    whatsappNumber = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    occupantType = serializers.CharField(source='occupant_type', read_only=True)
    photoUrl = serializers.SerializerMethodField()
    studentId = serializers.CharField(source='student_id_code', allow_blank=True, required=False)
    emergencyContactName = serializers.CharField(
        source='emergency_contact_name',
        read_only=True,
    )
    emergencyContactPhone = serializers.CharField(
        source='emergency_contact_phone',
        read_only=True,
    )
    nidNumber = serializers.CharField(source='nid_number', read_only=True)
    permanentAddress = serializers.CharField(source='permanent_address', read_only=True)
    seatNumber = serializers.CharField(source='seat_number', allow_blank=True, required=False)
    roomNumber = serializers.SerializerMethodField()
    joinedDate = serializers.DateField(source='joined_date')
    leftDate = serializers.DateField(source='left_date', allow_null=True, read_only=True)
    monthlyFee = serializers.FloatField(source='monthly_fee')
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    isSystemUser = serializers.SerializerMethodField()

    class Meta:
        model = MessStudent
        fields = (
            'id',
            'messId',
            'messName',
            'userId',
            'isSystemUser',
            'name',
            'phone',
            'whatsappNumber',
            'email',
            'occupantType',
            'photoUrl',
            'studentId',
            'university',
            'organization',
            'designation',
            'emergencyContactName',
            'emergencyContactPhone',
            'nidNumber',
            'permanentAddress',
            'notes',
            'seatNumber',
            'roomNumber',
            'joinedDate',
            'leftDate',
            'monthlyFee',
            'isActive',
        )

    def get_userId(self, obj) -> str:
        return str(obj.user_id) if obj.user_id else ''

    def get_isSystemUser(self, obj) -> bool:
        return bool(obj.user_id)

    def get_name(self, obj) -> str:
        from mess.services.identity import member_display_name

        return member_display_name(obj)

    def get_whatsappNumber(self, obj) -> str:
        user = getattr(obj, 'user', None)
        if user is not None and (user.whatsapp_number or '').strip():
            return user.whatsapp_number.strip()
        return (obj.whatsapp_number or '').strip()

    def get_email(self, obj) -> str:
        user = getattr(obj, 'user', None)
        if user is not None and (user.email or '').strip():
            return user.email.strip()
        return (obj.email or '').strip()

    def get_photoUrl(self, obj) -> str:
        from mess.services.identity import member_photo_url

        return member_photo_url(obj, request=self.context.get('request'))

    def get_roomNumber(self, obj) -> str:
        return obj.seat.room_number if obj.seat_id else ''


class StudentAssignSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20)
    whatsappNumber = WhatsAppNumberField(default='')
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    occupantType = serializers.ChoiceField(
        choices=OccupantType.choices,
        required=False,
        default=OccupantType.STUDENT,
    )
    photoUrl = serializers.URLField(required=False, allow_blank=True, default='')
    studentId = serializers.CharField(required=False, allow_blank=True, default='')
    university = serializers.CharField(required=False, allow_blank=True, default='')
    organization = serializers.CharField(required=False, allow_blank=True, default='')
    designation = serializers.CharField(required=False, allow_blank=True, default='')
    emergencyContactName = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
    )
    emergencyContactPhone = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
    )
    nidNumber = serializers.CharField(required=False, allow_blank=True, default='')
    permanentAddress = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    seatNumber = serializers.CharField(required=False, allow_blank=True, default='')
    joinedDate = serializers.DateField(required=False, allow_null=True)
    monthlyFee = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )


class StudentUpdateSerializer(serializers.Serializer):
    """Partial edit of one member — every field is optional."""

    name = serializers.CharField(max_length=255, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    whatsappNumber = WhatsAppNumberField()
    email = serializers.EmailField(required=False, allow_blank=True)
    occupantType = serializers.ChoiceField(choices=OccupantType.choices, required=False)
    photoUrl = serializers.URLField(required=False, allow_blank=True)
    studentId = serializers.CharField(required=False, allow_blank=True)
    university = serializers.CharField(required=False, allow_blank=True)
    organization = serializers.CharField(required=False, allow_blank=True)
    designation = serializers.CharField(required=False, allow_blank=True)
    emergencyContactName = serializers.CharField(required=False, allow_blank=True)
    emergencyContactPhone = serializers.CharField(required=False, allow_blank=True)
    nidNumber = serializers.CharField(required=False, allow_blank=True)
    permanentAddress = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    seatNumber = serializers.CharField(required=False, allow_blank=True)
    vacateSeat = serializers.BooleanField(required=False)
    joinedDate = serializers.DateField(required=False)
    leftDate = serializers.DateField(required=False, allow_null=True)
    monthlyFee = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    isActive = serializers.BooleanField(required=False)


class SeatSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    seatNumber = serializers.CharField(source='seat_number')
    roomNumber = serializers.CharField(source='room_number')
    studentId = serializers.SerializerMethodField()

    class Meta:
        model = Seat
        fields = (
            'id',
            'seatNumber',
            'roomNumber',
            'status',
            'studentId',
            'messId',
        )

    def get_studentId(self, obj):
        if obj.student_id:
            return str(obj.student_id)
        return None


class SeatUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['available', 'occupied'], required=False)
    vacate = serializers.BooleanField(required=False, default=False)


class NoticeAckSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    userName = serializers.CharField(source='user_name', read_only=True)
    acknowledgedAt = serializers.DateTimeField(source='acknowledged_at', read_only=True)

    class Meta:
        model = MessNoticeAck
        fields = ('userId', 'userName', 'acknowledgedAt')


class NoticeSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    expiryDate = serializers.DateField(source='expiry_date', allow_null=True, required=False)
    pdfUrl = serializers.CharField(source='pdf_url', allow_blank=True, required=False)
    imageUrls = serializers.JSONField(source='image_urls', required=False)
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    acknowledgments = NoticeAckSerializer(many=True, read_only=True)

    class Meta:
        model = MessNotice
        fields = (
            'id',
            'title',
            'content',
            'date',
            'priority',
            'messId',
            'category',
            'expiryDate',
            'pdfUrl',
            'imageUrls',
            'createdBy',
            'createdAt',
            'acknowledgments',
        )

    def get_createdBy(self, obj):
        return str(obj.created_by_id) if obj.created_by_id else ''


class NoticeWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    date = serializers.DateField()
    priority = serializers.ChoiceField(choices=['high', 'medium', 'low'])
    category = serializers.ChoiceField(
        choices=[
            'general', 'payment', 'maintenance', 'event',
            'announcement', 'rule', 'other',
        ],
        required=False,
        default='general',
    )
    expiryDate = serializers.DateField(required=False, allow_null=True)
    pdfUrl = serializers.CharField(required=False, allow_blank=True, default='')
    imageUrls = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )


class DailyMenuSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = DailyMenu
        fields = (
            'id',
            'messId',
            'date',
            'breakfast',
            'lunch',
            'dinner',
            'snack',
            'notes',
            'createdBy',
            'createdAt',
            'updatedAt',
        )

    def get_createdBy(self, obj):
        return str(obj.created_by_id) if obj.created_by_id else ''


class DailyMenuWriteSerializer(serializers.Serializer):
    date = serializers.DateField()
    breakfast = serializers.ListField(required=False, default=list)
    lunch = serializers.ListField(required=False, default=list)
    dinner = serializers.ListField(required=False, default=list)
    snack = serializers.ListField(required=False, default=list)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class WeeklyScheduleSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    weekStartDate = serializers.DateField(source='week_start_date')
    weekEndDate = serializers.DateField(source='week_end_date')
    isActive = serializers.BooleanField(source='is_active')
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = WeeklySchedule
        fields = (
            'id',
            'messId',
            'weekStartDate',
            'weekEndDate',
            'schedule',
            'isActive',
            'createdBy',
            'createdAt',
            'updatedAt',
        )

    def get_createdBy(self, obj):
        return str(obj.created_by_id) if obj.created_by_id else ''


class WeeklyScheduleWriteSerializer(serializers.Serializer):
    weekStartDate = serializers.DateField(required=False)
    weekEndDate = serializers.DateField(required=False)
    schedule = serializers.DictField(required=False)
    isActive = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        # Create requires full payload; PATCH may be partial.
        if not self.partial:
            missing = [
                name
                for name in ('weekStartDate', 'weekEndDate', 'schedule')
                if name not in attrs
            ]
            if missing:
                raise serializers.ValidationError(
                    {name: 'This field is required.' for name in missing}
                )
        return attrs


class MealTimingSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = MealTiming
        fields = ('messId', 'breakfast', 'lunch', 'dinner', 'snack', 'updatedAt')


class MealTimingWriteSerializer(serializers.Serializer):
    breakfast = serializers.DictField(required=False)
    lunch = serializers.DictField(required=False)
    dinner = serializers.DictField(required=False)
    snack = serializers.DictField(required=False)


class MealPreferenceSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = MealPreference
        fields = ('id', 'userId', 'messId', 'preferences', 'createdAt', 'updatedAt')


class AttendanceRecordSerializer(serializers.ModelSerializer):
    studentId = serializers.UUIDField(source='student_id', read_only=True)
    studentName = serializers.CharField(source='student_name', read_only=True)
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    checkInTime = serializers.DateTimeField(source='check_in_time', allow_null=True)
    checkOutTime = serializers.DateTimeField(source='check_out_time', allow_null=True)
    mealCategory = serializers.CharField(source='meal_category', allow_blank=True)
    markedBy = serializers.SerializerMethodField()
    markedAt = serializers.DateTimeField(source='marked_at', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = (
            'id',
            'studentId',
            'studentName',
            'messId',
            'date',
            'status',
            'type',
            'checkInTime',
            'checkOutTime',
            'mealCategory',
            'notes',
            'markedBy',
            'markedAt',
        )

    def get_markedBy(self, obj):
        return str(obj.marked_by_id) if obj.marked_by_id else ''


class AttendanceMarkSerializer(serializers.Serializer):
    studentId = serializers.UUIDField()
    date = serializers.DateField()
    status = serializers.ChoiceField(
        choices=[
            'present', 'absent', 'late', 'excused',
            'meal_attended', 'meal_absent',
        ],
    )
    type = serializers.ChoiceField(choices=['general', 'meal', 'both'], default='general')
    checkInTime = serializers.DateTimeField(required=False, allow_null=True)
    checkOutTime = serializers.DateTimeField(required=False, allow_null=True)
    mealCategory = serializers.ChoiceField(
        choices=['breakfast', 'lunch', 'dinner', 'snack'],
        required=False,
        allow_blank=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class AttendanceBulkSerializer(serializers.Serializer):
    # Optional fallback: every record already carries its own required date.
    date = serializers.DateField(required=False)
    records = AttendanceMarkSerializer(many=True)


class SMSTemplateSerializer(serializers.ModelSerializer):
    messId = serializers.SerializerMethodField()
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = SMSTemplate
        fields = (
            'id',
            'name',
            'content',
            'variables',
            'category',
            'messId',
            'createdBy',
            'createdAt',
            'updatedAt',
        )

    def get_messId(self, obj):
        return str(obj.mess_id) if obj.mess_id else None

    def get_createdBy(self, obj):
        return str(obj.created_by_id) if obj.created_by_id else ''


class SMSTemplateWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    content = serializers.CharField()
    variables = serializers.ListField(required=False, default=list)
    category = serializers.CharField(required=False, allow_blank=True, default='')


class SMSGroupSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    memberIds = serializers.JSONField(source='member_ids')
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = SMSGroup
        fields = (
            'id',
            'name',
            'description',
            'messId',
            'memberIds',
            'createdBy',
            'createdAt',
            'updatedAt',
        )

    def get_createdBy(self, obj):
        return str(obj.created_by_id) if obj.created_by_id else ''


class SMSGroupWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    memberIds = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class SMSMessageSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    messName = serializers.CharField(source='mess.name', read_only=True)
    templateId = serializers.SerializerMethodField()
    recipientType = serializers.CharField(source='recipient_type')
    totalRecipients = serializers.IntegerField(source='total_recipients', read_only=True)
    scheduledAt = serializers.DateTimeField(source='scheduled_at', allow_null=True)
    sentAt = serializers.DateTimeField(source='sent_at', allow_null=True)
    sentBy = serializers.SerializerMethodField()
    sentByName = serializers.SerializerMethodField()
    sentByPhone = serializers.SerializerMethodField()
    errorMessage = serializers.CharField(source='error_message', allow_blank=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = SMSMessage
        fields = (
            'id',
            'messId',
            'messName',
            'templateId',
            'content',
            'recipientType',
            'recipients',
            'totalRecipients',
            'successful',
            'failed',
            'status',
            'scheduledAt',
            'sentAt',
            'sentBy',
            'sentByName',
            'sentByPhone',
            'gateway',
            'cost',
            'errorMessage',
            'metadata',
            'createdAt',
        )

    def get_templateId(self, obj):
        return str(obj.template_id) if obj.template_id else None

    def get_sentBy(self, obj):
        return str(obj.sent_by_id) if obj.sent_by_id else ''

    def get_sentByName(self, obj):
        if not obj.sent_by_id:
            return ''
        return getattr(obj.sent_by, 'name', '') or ''

    def get_sentByPhone(self, obj):
        if not obj.sent_by_id:
            return ''
        return getattr(obj.sent_by, 'phone', '') or ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['cost'] = _money(instance.cost)
        return data


class SMSSendSerializer(serializers.Serializer):
    content = serializers.CharField()
    recipientType = serializers.ChoiceField(
        choices=['all', 'group', 'individual', 'custom'],
        default='all',
    )
    templateId = serializers.UUIDField(required=False, allow_null=True)
    groupId = serializers.UUIDField(required=False, allow_null=True)
    studentIds = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
    gateway = serializers.CharField(required=False, allow_blank=True, default='')


class MessRuleSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    requiresAcceptance = serializers.BooleanField(source='requires_acceptance')
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    effectiveDate = serializers.DateField(source='effective_date', allow_null=True)
    expiryDate = serializers.DateField(source='expiry_date', allow_null=True)

    class Meta:
        model = MessRule
        fields = (
            'id',
            'messId',
            'title',
            'description',
            'category',
            'severity',
            'penalty',
            'status',
            'requiresAcceptance',
            'createdBy',
            'createdAt',
            'updatedAt',
            'effectiveDate',
            'expiryDate',
        )

    def get_createdBy(self, obj):
        return str(obj.created_by_id) if obj.created_by_id else ''


class MessRuleWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    category = serializers.ChoiceField(
        choices=[
            'general', 'payment', 'attendance', 'meal',
            'behavior', 'facility', 'other',
        ],
    )
    severity = serializers.ChoiceField(
        choices=['minor', 'moderate', 'major', 'critical'],
    )
    penalty = serializers.CharField(required=False, allow_blank=True, default='')
    status = serializers.ChoiceField(
        choices=['active', 'inactive', 'archived'],
        required=False,
        default='active',
    )
    requiresAcceptance = serializers.BooleanField(required=False, default=False)
    effectiveDate = serializers.DateField(required=False, allow_null=True)
    expiryDate = serializers.DateField(required=False, allow_null=True)

    def to_internal_value(self, data):
        # HTML date inputs send "" when cleared — treat as null.
        if isinstance(data, dict):
            data = {
                **data,
                **{
                    key: None
                    for key in ('effectiveDate', 'expiryDate')
                    if data.get(key) == ''
                },
            }
        return super().to_internal_value(data)


class RuleAcceptanceSerializer(serializers.ModelSerializer):
    ruleId = serializers.UUIDField(source='rule_id', read_only=True)
    studentId = serializers.UUIDField(source='student_id', read_only=True)
    studentName = serializers.CharField(source='student_name', read_only=True)
    acceptedAt = serializers.DateTimeField(source='accepted_at', read_only=True)
    acceptedBy = serializers.SerializerMethodField()
    ipAddress = serializers.CharField(source='ip_address', allow_null=True)
    userAgent = serializers.CharField(source='user_agent', allow_blank=True)

    class Meta:
        model = RuleAcceptance
        fields = (
            'id',
            'ruleId',
            'studentId',
            'studentName',
            'acceptedAt',
            'acceptedBy',
            'ipAddress',
            'userAgent',
        )

    def get_acceptedBy(self, obj):
        return str(obj.accepted_by_id) if obj.accepted_by_id else ''


class RuleViolationSerializer(serializers.ModelSerializer):
    ruleId = serializers.UUIDField(source='rule_id', read_only=True)
    ruleTitle = serializers.CharField(source='rule_title', read_only=True)
    studentId = serializers.UUIDField(source='student_id', read_only=True)
    studentName = serializers.CharField(source='student_name', read_only=True)
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    violationDate = serializers.DateField(source='violation_date')
    reportedBy = serializers.SerializerMethodField()
    reportedAt = serializers.DateTimeField(source='reported_at', read_only=True)
    resolvedAt = serializers.DateTimeField(source='resolved_at', allow_null=True)
    resolvedBy = serializers.SerializerMethodField()
    resolutionNotes = serializers.CharField(source='resolution_notes', allow_blank=True)

    class Meta:
        model = RuleViolation
        fields = (
            'id',
            'ruleId',
            'ruleTitle',
            'studentId',
            'studentName',
            'messId',
            'violationDate',
            'description',
            'severity',
            'penalty',
            'status',
            'reportedBy',
            'reportedAt',
            'resolvedAt',
            'resolvedBy',
            'resolutionNotes',
            'evidence',
        )

    def get_reportedBy(self, obj):
        return str(obj.reported_by_id) if obj.reported_by_id else ''

    def get_resolvedBy(self, obj):
        return str(obj.resolved_by_id) if obj.resolved_by_id else None


class RuleViolationWriteSerializer(serializers.Serializer):
    ruleId = serializers.UUIDField()
    studentId = serializers.UUIDField()
    violationDate = serializers.DateField()
    description = serializers.CharField()
    severity = serializers.ChoiceField(
        choices=['minor', 'moderate', 'major', 'critical'],
    )
    penalty = serializers.DictField(required=False, allow_null=True)
    evidence = serializers.ListField(required=False, default=list)


class RuleViolationPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['pending', 'resolved', 'appealed', 'dismissed'],
        required=False,
    )
    resolutionNotes = serializers.CharField(required=False, allow_blank=True)


class MessExpenseSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    amount = serializers.SerializerMethodField()
    receiptUrl = serializers.CharField(source='receipt_url', allow_blank=True)
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = MessExpense
        fields = (
            'id',
            'messId',
            'category',
            'description',
            'amount',
            'date',
            'receiptUrl',
            'vendor',
            'notes',
            'createdBy',
            'createdAt',
            'updatedAt',
        )

    def get_amount(self, obj):
        return _money(obj.amount)

    def get_createdBy(self, obj):
        return str(obj.created_by_id) if obj.created_by_id else ''


class MessExpenseWriteSerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=['food', 'utilities', 'maintenance', 'staff', 'supplies', 'other'],
    )
    description = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    date = serializers.DateField()
    receiptUrl = serializers.CharField(required=False, allow_blank=True, default='')
    vendor = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class MessBillGetOrCreateSerializer(serializers.Serializer):
    tenantName = serializers.CharField(max_length=255)
    seatNumber = serializers.CharField(required=False, allow_blank=True, default='')
    monthlyFee = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    studentId = serializers.CharField(required=False, allow_blank=True, default='')
