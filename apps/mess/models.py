from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel


DEFAULT_MEAL_TIMING = {
    'breakfast': {'startTime': '07:00', 'endTime': '09:00', 'enabled': True},
    'lunch': {'startTime': '12:00', 'endTime': '14:00', 'enabled': True},
    'dinner': {'startTime': '19:00', 'endTime': '21:00', 'enabled': True},
    'snack': {'startTime': '16:00', 'endTime': '17:00', 'enabled': False},
}


class MessGender(models.TextChoices):
    MALE = 'male', 'Male'
    FEMALE = 'female', 'Female'
    MIXED = 'mixed', 'Mixed'


class SeatStatus(models.TextChoices):
    AVAILABLE = 'available', 'Available'
    OCCUPIED = 'occupied', 'Occupied'


class NoticePriority(models.TextChoices):
    HIGH = 'high', 'High'
    MEDIUM = 'medium', 'Medium'
    LOW = 'low', 'Low'


class NoticeCategory(models.TextChoices):
    GENERAL = 'general', 'General'
    PAYMENT = 'payment', 'Payment'
    MAINTENANCE = 'maintenance', 'Maintenance'
    EVENT = 'event', 'Event'
    ANNOUNCEMENT = 'announcement', 'Announcement'
    RULE = 'rule', 'Rule'
    OTHER = 'other', 'Other'


class AttendanceStatus(models.TextChoices):
    PRESENT = 'present', 'Present'
    ABSENT = 'absent', 'Absent'
    LATE = 'late', 'Late'
    EXCUSED = 'excused', 'Excused'
    MEAL_ATTENDED = 'meal_attended', 'Meal Attended'
    MEAL_ABSENT = 'meal_absent', 'Meal Absent'


class AttendanceType(models.TextChoices):
    GENERAL = 'general', 'General'
    MEAL = 'meal', 'Meal'
    BOTH = 'both', 'Both'


class MealCategory(models.TextChoices):
    BREAKFAST = 'breakfast', 'Breakfast'
    LUNCH = 'lunch', 'Lunch'
    DINNER = 'dinner', 'Dinner'
    SNACK = 'snack', 'Snack'


class SMSStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'
    DELIVERED = 'delivered', 'Delivered'


class SMSRecipientType(models.TextChoices):
    ALL = 'all', 'All'
    GROUP = 'group', 'Group'
    INDIVIDUAL = 'individual', 'Individual'
    CUSTOM = 'custom', 'Custom'


class SMSTemplateCategory(models.TextChoices):
    PAYMENT = 'payment', 'Payment'
    ATTENDANCE = 'attendance', 'Attendance'
    NOTICE = 'notice', 'Notice'
    REMINDER = 'reminder', 'Reminder'
    GENERAL = 'general', 'General'


class RuleStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    ARCHIVED = 'archived', 'Archived'


class RuleCategory(models.TextChoices):
    GENERAL = 'general', 'General'
    PAYMENT = 'payment', 'Payment'
    ATTENDANCE = 'attendance', 'Attendance'
    MEAL = 'meal', 'Meal'
    BEHAVIOR = 'behavior', 'Behavior'
    FACILITY = 'facility', 'Facility'
    OTHER = 'other', 'Other'


class ViolationSeverity(models.TextChoices):
    MINOR = 'minor', 'Minor'
    MODERATE = 'moderate', 'Moderate'
    MAJOR = 'major', 'Major'
    CRITICAL = 'critical', 'Critical'


class ViolationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    RESOLVED = 'resolved', 'Resolved'
    APPEALED = 'appealed', 'Appealed'
    DISMISSED = 'dismissed', 'Dismissed'


class ExpenseCategory(models.TextChoices):
    FOOD = 'food', 'Food'
    UTILITIES = 'utilities', 'Utilities'
    MAINTENANCE = 'maintenance', 'Maintenance'
    STAFF = 'staff', 'Staff'
    SUPPLIES = 'supplies', 'Supplies'
    OTHER = 'other', 'Other'


class Mess(UUIDModel, TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='messes',
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=80, db_index=True)
    total_seats = models.PositiveIntegerField(default=0)
    available_seats = models.PositiveIntegerField(default=0)
    monthly_fee = models.DecimalField(max_digits=12, decimal_places=2)
    gender = models.CharField(max_length=10, choices=MessGender.choices)
    facilities = models.JSONField(default=list, blank=True)
    images = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, default='')
    owner_name = models.CharField(max_length=255, blank=True, default='')
    owner_phone = models.CharField(max_length=20, blank=True, default='')
    is_deleted = models.BooleanField(default=False, db_index=True)
    featured = models.BooleanField(default=False, db_index=True)
    featured_until = models.DateTimeField(null=True, blank=True)
    last_confirmed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    flagged_unavailable_at = models.DateTimeField(null=True, blank=True)
    listing = models.ForeignKey(
        'listings.Property',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_messes',
        help_text='Public listing that should mirror this mess seat inventory.',
    )
    live_status = models.JSONField(
        default=dict,
        blank=True,
        help_text='Public live utilities: water/electricity/wifi/meals → ok|warn|down.',
    )
    live_status_updated_at = models.DateTimeField(null=True, blank=True)
    # Public meal / guest pricing (seeker-facing)
    meals_per_day = models.PositiveSmallIntegerField(default=3)
    vegetarian_option = models.BooleanField(default=False)
    meal_monthly_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Optional fixed monthly meal charge shown on public profile.',
    )
    guest_meal_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Price per guest meal (মিল).',
    )
    meal_off_policy = models.TextField(
        blank=True,
        default='',
        help_text='Rules for turning meals on/off (মিল বন্ধ).',
    )
    fish_meat_days_per_week = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Typical fish/meat days per week (0–7).',
    )
    # Utility profiles for reliability scores
    water_profile = models.JSONField(default=dict, blank=True)
    electricity_profile = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'mess_mess'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['city', 'gender']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.owner_id and not self.owner_name:
            owner = self.owner
            self.owner_name = owner.name or f'User {owner.phone[-4:]}'
            self.owner_phone = owner.phone
        super().save(*args, **kwargs)

    def refresh_seat_counts(self):
        seats = self.seats.filter(is_deleted=False)
        self.total_seats = seats.count()
        self.available_seats = seats.filter(status=SeatStatus.AVAILABLE).count()
        self.save(update_fields=['total_seats', 'available_seats', 'updated_at'])
        from listings.services.inventory import sync_mess_listing

        sync_mess_listing(self)


class Seat(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='seats')
    seat_number = models.CharField(max_length=32)
    room_number = models.CharField(max_length=32)
    status = models.CharField(
        max_length=20,
        choices=SeatStatus.choices,
        default=SeatStatus.AVAILABLE,
    )
    student = models.ForeignKey(
        'MessStudent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_seat',
    )
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'mess_seat'
        ordering = ('room_number', 'seat_number')
        constraints = [
            models.UniqueConstraint(
                fields=['mess', 'seat_number'],
                name='unique_seat_number_per_mess',
            ),
        ]

    def __str__(self):
        return f'{self.mess.name} — {self.seat_number}'


class MessStudent(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='students')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mess_enrollments',
    )
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, default='')
    student_id_code = models.CharField(max_length=64, blank=True, default='')
    university = models.CharField(max_length=255, blank=True, default='')
    seat = models.OneToOneField(
        Seat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrollment',
    )
    seat_number = models.CharField(max_length=32, blank=True, default='')
    joined_date = models.DateField()
    monthly_fee = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'mess_student'
        ordering = ('-joined_date',)
        indexes = [
            models.Index(fields=['mess', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f'{self.name} @ {self.mess.name}'


class MessNotice(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='notices')
    title = models.CharField(max_length=255)
    content = models.TextField()
    date = models.DateField()
    priority = models.CharField(max_length=10, choices=NoticePriority.choices)
    category = models.CharField(
        max_length=20,
        choices=NoticeCategory.choices,
        default=NoticeCategory.GENERAL,
    )
    expiry_date = models.DateField(null=True, blank=True)
    pdf_url = models.URLField(blank=True, default='')
    image_urls = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='mess_notices_created',
    )
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'mess_notice'
        ordering = ('-date', '-created_at')


class MessNoticeAck(UUIDModel, TimestampedModel):
    notice = models.ForeignKey(
        MessNotice,
        on_delete=models.CASCADE,
        related_name='acknowledgments',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mess_notice_acks',
    )
    user_name = models.CharField(max_length=255, blank=True, default='')
    acknowledged_at = models.DateTimeField()

    class Meta:
        db_table = 'mess_notice_ack'
        constraints = [
            models.UniqueConstraint(
                fields=['notice', 'user'],
                name='unique_notice_ack_per_user',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.user_id and not self.user_name:
            user = self.user
            self.user_name = user.name or f'User {user.phone[-4:]}'
        super().save(*args, **kwargs)


class DailyMenu(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='daily_menus')
    date = models.DateField()
    breakfast = models.JSONField(default=list, blank=True)
    lunch = models.JSONField(default=list, blank=True)
    dinner = models.JSONField(default=list, blank=True)
    snack = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='daily_menus_created',
    )

    class Meta:
        db_table = 'mess_daily_menu'
        ordering = ('-date',)
        constraints = [
            models.UniqueConstraint(
                fields=['mess', 'date'],
                name='unique_daily_menu_per_date',
            ),
        ]


class WeeklySchedule(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(
        Mess,
        on_delete=models.CASCADE,
        related_name='weekly_schedules',
    )
    week_start_date = models.DateField()
    week_end_date = models.DateField()
    schedule = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='weekly_schedules_created',
    )

    class Meta:
        db_table = 'mess_weekly_schedule'
        ordering = ('-week_start_date',)


class MealTiming(UUIDModel):
    mess = models.OneToOneField(
        Mess,
        on_delete=models.CASCADE,
        related_name='meal_timing',
    )
    breakfast = models.JSONField(default=dict, blank=True)
    lunch = models.JSONField(default=dict, blank=True)
    dinner = models.JSONField(default=dict, blank=True)
    snack = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mess_meal_timing'

    def save(self, *args, **kwargs):
        if not self.breakfast:
            self.breakfast = dict(DEFAULT_MEAL_TIMING['breakfast'])
        if not self.lunch:
            self.lunch = dict(DEFAULT_MEAL_TIMING['lunch'])
        if not self.dinner:
            self.dinner = dict(DEFAULT_MEAL_TIMING['dinner'])
        if not self.snack:
            self.snack = dict(DEFAULT_MEAL_TIMING['snack'])
        super().save(*args, **kwargs)


class MealPreference(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meal_preferences',
    )
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='meal_preferences')
    preferences = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'mess_meal_preference'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'mess'],
                name='unique_meal_preference_per_user_mess',
            ),
        ]


class AttendanceRecord(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='attendance_records')
    student = models.ForeignKey(
        MessStudent,
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    student_name = models.CharField(max_length=255)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=AttendanceStatus.choices)
    type = models.CharField(max_length=10, choices=AttendanceType.choices)
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    meal_category = models.CharField(
        max_length=10,
        choices=MealCategory.choices,
        blank=True,
        default='',
    )
    notes = models.TextField(blank=True, default='')
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='attendance_marked',
    )
    marked_at = models.DateTimeField()

    class Meta:
        db_table = 'mess_attendance_record'
        ordering = ('-date', '-marked_at')
        indexes = [
            models.Index(fields=['mess', 'date']),
            models.Index(fields=['student', 'date']),
        ]


class SMSTemplate(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(
        Mess,
        on_delete=models.CASCADE,
        related_name='sms_templates',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    content = models.TextField()
    variables = models.JSONField(default=list, blank=True)
    category = models.CharField(
        max_length=20,
        choices=SMSTemplateCategory.choices,
        blank=True,
        default='',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sms_templates_created',
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'mess_sms_template'
        ordering = ('-updated_at',)


class SMSGroup(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='sms_groups')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    member_ids = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sms_groups_created',
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'mess_sms_group'
        ordering = ('-updated_at',)


class SMSMessage(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='sms_messages')
    template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
    )
    content = models.TextField()
    recipient_type = models.CharField(max_length=20, choices=SMSRecipientType.choices)
    recipients = models.JSONField(default=list, blank=True)
    total_recipients = models.PositiveIntegerField(default=0)
    successful = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=SMSStatus.choices,
        default=SMSStatus.PENDING,
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sms_messages_sent',
    )
    gateway = models.CharField(max_length=20, blank=True, default='')
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    error_message = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'mess_sms_message'
        ordering = ('-created_at',)


class MessRule(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='rules')
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=RuleCategory.choices)
    severity = models.CharField(max_length=20, choices=ViolationSeverity.choices)
    penalty = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=RuleStatus.choices,
        default=RuleStatus.ACTIVE,
    )
    requires_acceptance = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='mess_rules_created',
    )
    effective_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'mess_rule'
        ordering = ('-created_at',)


class RuleAcceptance(UUIDModel, TimestampedModel):
    rule = models.ForeignKey(MessRule, on_delete=models.CASCADE, related_name='acceptances')
    student = models.ForeignKey(MessStudent, on_delete=models.CASCADE, related_name='rule_acceptances')
    student_name = models.CharField(max_length=255, blank=True, default='')
    accepted_at = models.DateTimeField()
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='rule_acceptances',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')

    class Meta:
        db_table = 'mess_rule_acceptance'
        constraints = [
            models.UniqueConstraint(
                fields=['rule', 'student'],
                name='unique_rule_acceptance_per_student',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.student_id and not self.student_name:
            self.student_name = self.student.name
        super().save(*args, **kwargs)


class RuleViolation(UUIDModel, TimestampedModel):
    rule = models.ForeignKey(MessRule, on_delete=models.CASCADE, related_name='violations')
    rule_title = models.CharField(max_length=255, blank=True, default='')
    student = models.ForeignKey(MessStudent, on_delete=models.CASCADE, related_name='violations')
    student_name = models.CharField(max_length=255)
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='rule_violations')
    violation_date = models.DateField()
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=ViolationSeverity.choices)
    penalty = models.JSONField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ViolationStatus.choices,
        default=ViolationStatus.PENDING,
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='violations_reported',
    )
    reported_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='violations_resolved',
    )
    resolution_notes = models.TextField(blank=True, default='')
    evidence = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'mess_rule_violation'
        ordering = ('-violation_date', '-reported_at')

    def save(self, *args, **kwargs):
        if self.rule_id and not self.rule_title:
            self.rule_title = self.rule.title
        super().save(*args, **kwargs)


class MessExpense(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='expenses')
    category = models.CharField(max_length=20, choices=ExpenseCategory.choices)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    receipt_url = models.URLField(blank=True, default='')
    vendor = models.CharField(max_length=255, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='mess_expenses_created',
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'mess_expense'
        ordering = ('-date', '-created_at')


class MealOffStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class MonthCloseStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    CLOSED = 'closed', 'Closed'


class MemberMealLog(UUIDModel, TimestampedModel):
    """Per-member daily meal counts for মিল হিসাব (breakfast/lunch/dinner)."""

    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='meal_logs')
    student = models.ForeignKey(
        MessStudent,
        on_delete=models.CASCADE,
        related_name='meal_logs',
    )
    date = models.DateField(db_index=True)
    breakfast = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    lunch = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    dinner = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    guest_breakfast = models.PositiveSmallIntegerField(default=0)
    guest_lunch = models.PositiveSmallIntegerField(default=0)
    guest_dinner = models.PositiveSmallIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True, default='')
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meal_logs_marked',
    )

    class Meta:
        db_table = 'mess_member_meal_log'
        ordering = ('-date',)
        constraints = [
            models.UniqueConstraint(
                fields=['mess', 'student', 'date'],
                name='unique_meal_log_per_student_date',
            ),
        ]
        indexes = [
            models.Index(fields=['mess', 'date']),
        ]

    @property
    def member_meal_total(self):
        return self.breakfast + self.lunch + self.dinner

    @property
    def guest_meal_total(self):
        return self.guest_breakfast + self.guest_lunch + self.guest_dinner


class MealOffRequest(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='meal_off_requests')
    student = models.ForeignKey(
        MessStudent,
        on_delete=models.CASCADE,
        related_name='meal_off_requests',
    )
    start_date = models.DateField()
    end_date = models.DateField()
    meals = models.JSONField(
        default=dict,
        blank=True,
        help_text='Which meals to skip, e.g. {breakfast:true, lunch:true, dinner:true}',
    )
    reason = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=MealOffStatus.choices,
        default=MealOffStatus.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meal_off_reviews',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'mess_meal_off_request'
        ordering = ('-created_at',)


class MemberDeposit(UUIDModel, TimestampedModel):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='member_deposits')
    student = models.ForeignKey(
        MessStudent,
        on_delete=models.CASCADE,
        related_name='deposits',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    note = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mess_deposits_created',
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'mess_member_deposit'
        ordering = ('-date', '-created_at')


class MessMonthClose(UUIDModel, TimestampedModel):
    """Month-end মিল হিসাব snapshot (bazaar → meal rate → member dues)."""

    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='month_closes')
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=20,
        choices=MonthCloseStatus.choices,
        default=MonthCloseStatus.OPEN,
        db_index=True,
    )
    bazaar_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fixed_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_meals = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    meal_rate = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    guest_meal_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mess_months_closed',
    )
    snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'mess_month_close'
        ordering = ('-year', '-month')
        constraints = [
            models.UniqueConstraint(
                fields=['mess', 'year', 'month'],
                name='unique_mess_month_close',
            ),
        ]


class MemberMonthBill(UUIDModel, TimestampedModel):
    month_close = models.ForeignKey(
        MessMonthClose,
        on_delete=models.CASCADE,
        related_name='member_bills',
    )
    student = models.ForeignKey(
        MessStudent,
        on_delete=models.CASCADE,
        related_name='month_bills',
    )
    student_name = models.CharField(max_length=255, blank=True, default='')
    meal_count = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    meal_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    guest_meals = models.PositiveIntegerField(default=0)
    guest_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fixed_share = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deposits = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = 'mess_member_month_bill'
        constraints = [
            models.UniqueConstraint(
                fields=['month_close', 'student'],
                name='unique_member_bill_per_close',
            ),
        ]
