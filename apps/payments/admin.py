from django.contrib import admin

from payments.models import (
    OwnerCollectionSettings,
    OwnerGatewayCredential,
    OwnerPayout,
    PaymentClaim,
    PaymentSchedule,
    PaymentTransaction,
    PaymentWebhookEvent,
    ScheduledPayment,
)


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_id',
        'bill_name',
        'amount',
        'payment_method',
        'status',
        'user',
        'created_at',
    )
    list_filter = ('status', 'payment_method')
    search_fields = ('transaction_id', 'bill_name', 'user__phone')
    readonly_fields = ('gateway_payload', 'created_at', 'updated_at')


@admin.register(ScheduledPayment)
class ScheduledPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'bill_name',
        'scheduled_date',
        'amount',
        'payment_method',
        'status',
        'user',
    )
    list_filter = ('status', 'payment_method')
    search_fields = ('bill_name', 'user__phone')


@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'payment_method', 'is_active', 'user')
    list_filter = ('is_active', 'recurring', 'frequency')
    search_fields = ('name', 'user__phone')


@admin.register(OwnerPayout)
class OwnerPayoutAdmin(admin.ModelAdmin):
    list_display = (
        'bill_name',
        'gross_amount',
        'net_amount',
        'status',
        'owner',
        'transaction_id',
    )
    list_filter = ('status', 'payment_method')
    search_fields = ('bill_name', 'transaction_id', 'owner__phone')


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('gateway', 'gateway_event_id', 'processed', 'created_at')
    list_filter = ('gateway', 'processed')
    search_fields = ('gateway_event_id',)
    readonly_fields = ('raw_payload', 'created_at', 'updated_at')


@admin.register(OwnerCollectionSettings)
class OwnerCollectionSettingsAdmin(admin.ModelAdmin):
    list_display = ('owner', 'collection_mode', 'platform_collect_enabled', 'bkash_number')
    list_filter = ('collection_mode', 'platform_collect_enabled')
    search_fields = ('owner__phone', 'bkash_number', 'nagad_number')


@admin.register(OwnerGatewayCredential)
class OwnerGatewayCredentialAdmin(admin.ModelAdmin):
    list_display = ('owner', 'gateway', 'merchant_number', 'is_active', 'is_sandbox')
    list_filter = ('gateway', 'is_active', 'is_sandbox')
    search_fields = ('owner__phone', 'merchant_number')
    readonly_fields = ('credentials',)


@admin.register(PaymentClaim)
class PaymentClaimAdmin(admin.ModelAdmin):
    list_display = (
        'amount',
        'payment_method',
        'status',
        'claimed_by',
        'transaction_id',
        'created_at',
    )
    list_filter = ('status', 'payment_method')
    search_fields = ('transaction_id', 'claimed_by__phone')
