from rest_framework import serializers

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
    ownerName = serializers.CharField(source='owner_name', read_only=True)
    ownerPhone = serializers.CharField(source='owner_phone', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    listingId = serializers.UUIDField(source='listing_id', read_only=True, allow_null=True)
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
            'gender',
            'facilities',
            'images',
            'description',
            'ownerName',
            'ownerPhone',
            'createdAt',
            'listingId',
            'featured',
            'lastConfirmedAt',
            'confirmedHoursAgo',
            'stale',
            'liveStatus',
            'mealSystem',
            'utilities',
            'bookUrl',
        )

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


class MessCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=80)
    monthlyFee = serializers.DecimalField(max_digits=12, decimal_places=2, source='monthly_fee')
    gender = serializers.ChoiceField(choices=['male', 'female', 'mixed'])
    facilities = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    images = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    totalSeats = serializers.IntegerField(source='total_seats', required=False, default=0)
    listingId = serializers.UUIDField(required=False, allow_null=True)

    def create_mess(self, owner):
        data = dict(self.validated_data)
        listing_id = data.pop('listingId', None)
        mess = Mess.objects.create(owner=owner, **data)
        from listings.services.inventory import attach_listing_to_mess

        attach_listing_to_mess(mess, listing_id)
        return mess


class StudentSerializer(serializers.ModelSerializer):
    messId = serializers.UUIDField(source='mess_id', read_only=True)
    userId = serializers.SerializerMethodField()
    studentId = serializers.CharField(source='student_id_code', allow_blank=True, required=False)
    seatNumber = serializers.CharField(source='seat_number', allow_blank=True, required=False)
    joinedDate = serializers.DateField(source='joined_date')
    monthlyFee = serializers.FloatField(source='monthly_fee')

    class Meta:
        model = MessStudent
        fields = (
            'id',
            'messId',
            'userId',
            'name',
            'phone',
            'email',
            'studentId',
            'university',
            'seatNumber',
            'joinedDate',
            'monthlyFee',
        )

    def get_userId(self, obj) -> str:
        return str(obj.user_id) if obj.user_id else ''


class StudentAssignSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    studentId = serializers.CharField(required=False, allow_blank=True, default='')
    university = serializers.CharField(required=False, allow_blank=True, default='')
    seatNumber = serializers.CharField(required=False, allow_blank=True, default='')
    monthlyFee = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )


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
    weekStartDate = serializers.DateField()
    weekEndDate = serializers.DateField()
    schedule = serializers.DictField()
    isActive = serializers.BooleanField(required=False, default=True)


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
    date = serializers.DateField()
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
    templateId = serializers.SerializerMethodField()
    recipientType = serializers.CharField(source='recipient_type')
    totalRecipients = serializers.IntegerField(source='total_recipients', read_only=True)
    scheduledAt = serializers.DateTimeField(source='scheduled_at', allow_null=True)
    sentAt = serializers.DateTimeField(source='sent_at', allow_null=True)
    sentBy = serializers.SerializerMethodField()
    errorMessage = serializers.CharField(source='error_message', allow_blank=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = SMSMessage
        fields = (
            'id',
            'messId',
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
