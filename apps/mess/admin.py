from django.contrib import admin

from core.admin import TimestampedModelAdmin
from mess.models import (
    AttendanceRecord,
    DailyMenu,
    MealOffRequest,
    MealPreference,
    MealTiming,
    MemberDeposit,
    MemberMealLog,
    MemberMonthBill,
    Mess,
    MessExpense,
    MessMonthClose,
    MessNotice,
    MessNoticeAck,
    MessRule,
    MessStudent,
    OwnerSMSAccount,
    RuleAcceptance,
    RuleViolation,
    Seat,
    SMSCreditLedger,
    SMSCreditPackage,
    SMSCreditPurchase,
    SMSGroup,
    SMSMessage,
    SMSTemplate,
    WeeklySchedule,
)


@admin.register(Mess)
class MessAdmin(TimestampedModelAdmin):
    list_display = (
        'name',
        'city',
        'owner_name',
        'total_seats',
        'available_seats',
        'listing',
        'is_deleted',
    )
    list_filter = ('city', 'gender', 'is_deleted')
    search_fields = ('name', 'owner_name', 'city')


@admin.register(Seat)
class SeatAdmin(TimestampedModelAdmin):
    list_display = ('seat_number', 'room_number', 'mess', 'status')
    list_filter = ('status',)


@admin.register(MessStudent)
class MessStudentAdmin(TimestampedModelAdmin):
    list_display = (
        'name',
        'mess',
        'occupant_type',
        'seat_number',
        'phone',
        'is_active',
    )
    list_filter = ('occupant_type', 'is_active', 'is_deleted')
    search_fields = (
        'name',
        'phone',
        'whatsapp_number',
        'university',
        'organization',
        'mess__name',
    )


@admin.register(MessNotice)
class MessNoticeAdmin(TimestampedModelAdmin):
    list_display = ('title', 'mess', 'priority', 'date', 'category')
    list_filter = ('priority', 'category')


@admin.register(MessNoticeAck)
class MessNoticeAckAdmin(TimestampedModelAdmin):
    list_display = ('notice', 'user', 'user_name', 'acknowledged_at')


@admin.register(DailyMenu)
class DailyMenuAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'date')


@admin.register(WeeklySchedule)
class WeeklyScheduleAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'week_start_date', 'week_end_date', 'is_active')


@admin.register(MealTiming)
class MealTimingAdmin(TimestampedModelAdmin):
    list_display = ('mess',)


@admin.register(MealPreference)
class MealPreferenceAdmin(TimestampedModelAdmin):
    list_display = ('user', 'mess')


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'student', 'date', 'status')
    list_filter = ('status',)


@admin.register(SMSTemplate)
class SMSTemplateAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'name', 'category')


@admin.register(SMSGroup)
class SMSGroupAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'name')


@admin.register(SMSMessage)
class SMSMessageAdmin(TimestampedModelAdmin):
    list_display = (
        'id',
        'mess',
        'sent_by',
        'recipient_type',
        'successful',
        'failed',
        'cost',
        'gateway',
        'status',
        'sent_at',
    )
    list_filter = ('status', 'gateway', 'recipient_type')
    search_fields = ('content', 'mess__name', 'sent_by__phone')


@admin.register(SMSCreditPackage)
class SMSCreditPackageAdmin(TimestampedModelAdmin):
    list_display = (
        'package_key',
        'label',
        'credits',
        'price_bdt',
        'is_active',
        'sort_order',
    )
    list_filter = ('is_active',)
    search_fields = ('package_key', 'label')


@admin.register(OwnerSMSAccount)
class OwnerSMSAccountAdmin(TimestampedModelAdmin):
    list_display = (
        'owner',
        'balance',
        'lifetime_granted',
        'lifetime_purchased',
        'lifetime_used',
        'free_quota_period',
    )
    search_fields = ('owner__phone', 'owner__name')


@admin.register(SMSCreditLedger)
class SMSCreditLedgerAdmin(TimestampedModelAdmin):
    list_display = ('account', 'entry_type', 'credits', 'balance_after')
    list_filter = ('entry_type',)


@admin.register(SMSCreditPurchase)
class SMSCreditPurchaseAdmin(TimestampedModelAdmin):
    list_display = ('owner', 'package_id', 'credits', 'amount_bdt', 'status', 'paid_at')
    list_filter = ('status', 'package_id')


@admin.register(MessRule)
class MessRuleAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'title', 'status')


@admin.register(RuleAcceptance)
class RuleAcceptanceAdmin(TimestampedModelAdmin):
    list_display = ('rule', 'student', 'accepted_at')


@admin.register(RuleViolation)
class RuleViolationAdmin(TimestampedModelAdmin):
    list_display = ('rule', 'student', 'status')


@admin.register(MessExpense)
class MessExpenseAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'category', 'description', 'amount', 'date')


@admin.register(MemberMealLog)
class MemberMealLogAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'student', 'date')


@admin.register(MealOffRequest)
class MealOffRequestAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'student', 'status', 'start_date', 'end_date')
    list_filter = ('status',)


@admin.register(MemberDeposit)
class MemberDepositAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'student', 'amount', 'date', 'status')


@admin.register(MessMonthClose)
class MessMonthCloseAdmin(TimestampedModelAdmin):
    list_display = ('mess', 'year', 'month', 'status')


@admin.register(MemberMonthBill)
class MemberMonthBillAdmin(TimestampedModelAdmin):
    list_display = ('month_close', 'student', 'student_name', 'meal_cost')
