from django.urls import path

from payments.views import (
    BkashWebhookView,
    NagadWebhookView,
    OwnerAnalyticsView,
    OwnerPayoutsView,
    PayBillView,
    PaymentHistoryView,
    PaymentSchedulesView,
    RecordCashView,
    RocketWebhookView,
    SandboxCompleteView,
    ScheduledPaymentCancelView,
    ScheduledPaymentDetailView,
    ScheduledPaymentsView,
    SettlePayoutView,
    TransactionDetailView,
)

urlpatterns = [
    path('payments/history/', PaymentHistoryView.as_view(), name='payments-history'),
    path('payments/scheduled/', ScheduledPaymentsView.as_view(), name='payments-scheduled'),
    path('payments/scheduled/<uuid:pk>/', ScheduledPaymentDetailView.as_view(), name='payments-scheduled-detail'),
    path('payments/scheduled/<uuid:pk>/cancel/', ScheduledPaymentCancelView.as_view(), name='payments-scheduled-cancel'),
    path('payments/schedules/', PaymentSchedulesView.as_view(), name='payments-schedules'),
    path('payments/pay-bill/', PayBillView.as_view(), name='payments-pay-bill'),
    path('payments/record-cash/', RecordCashView.as_view(), name='payments-record-cash'),
    path('payments/owner/payouts/', OwnerPayoutsView.as_view(), name='payments-owner-payouts'),
    path('payments/owner/analytics/', OwnerAnalyticsView.as_view(), name='payments-owner-analytics'),
    path('payments/owner/payouts/<uuid:pk>/settle/', SettlePayoutView.as_view(), name='payments-settle-payout'),
    path('payments/transactions/<str:txn_id>/', TransactionDetailView.as_view(), name='payments-transaction-detail'),
    path('payments/webhooks/bkash/', BkashWebhookView.as_view(), name='payments-webhook-bkash'),
    path('payments/webhooks/nagad/', NagadWebhookView.as_view(), name='payments-webhook-nagad'),
    path('payments/webhooks/rocket/', RocketWebhookView.as_view(), name='payments-webhook-rocket'),
    path('payments/sandbox/complete/', SandboxCompleteView.as_view(), name='payments-sandbox-complete'),
]
