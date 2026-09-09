from django.contrib import admin

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
class MessAdmin(admin.ModelAdmin):
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
class SeatAdmin(admin.ModelAdmin):
    list_display = ('seat_number', 'room_number', 'mess', 'status')
    list_filter = ('status',)


@admin.register(MessStudent)
class MessStudentAdmin(admin.ModelAdmin):
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
class MessNoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'mess', 'priority', 'date', 'category')
    list_filter = ('priority', 'category')


admin.site.register(MessNoticeAck)
admin.site.register(DailyMenu)
admin.site.register(WeeklySchedule)
admin.site.register(MealTiming)
admin.site.register(MealPreference)
admin.site.register(AttendanceRecord)
admin.site.register(SMSTemplate)
admin.site.register(SMSGroup)


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
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
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SMSCreditPackage)
class SMSCreditPackageAdmin(admin.ModelAdmin):
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
class OwnerSMSAccountAdmin(admin.ModelAdmin):
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
class SMSCreditLedgerAdmin(admin.ModelAdmin):
    list_display = ('account', 'entry_type', 'credits', 'balance_after', 'created_at')
    list_filter = ('entry_type',)


@admin.register(SMSCreditPurchase)
class SMSCreditPurchaseAdmin(admin.ModelAdmin):
    list_display = ('owner', 'package_id', 'credits', 'amount_bdt', 'status', 'paid_at')
    list_filter = ('status', 'package_id')


admin.site.register(MessRule)
admin.site.register(RuleAcceptance)
admin.site.register(RuleViolation)
admin.site.register(MessExpense)
admin.site.register(MemberMealLog)
admin.site.register(MealOffRequest)
admin.site.register(MemberDeposit)
admin.site.register(MessMonthClose)
admin.site.register(MemberMonthBill)
