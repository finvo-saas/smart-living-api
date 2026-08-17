from django.contrib import admin

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


@admin.register(Mess)
class MessAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'owner_name', 'total_seats', 'available_seats', 'is_deleted')
    list_filter = ('city', 'gender', 'is_deleted')
    search_fields = ('name', 'owner_name', 'city')


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('seat_number', 'room_number', 'mess', 'status')
    list_filter = ('status',)


@admin.register(MessStudent)
class MessStudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'mess', 'seat_number', 'phone', 'is_active')
    list_filter = ('is_active', 'is_deleted')


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
admin.site.register(SMSMessage)
admin.site.register(MessRule)
admin.site.register(RuleAcceptance)
admin.site.register(RuleViolation)
admin.site.register(MessExpense)
