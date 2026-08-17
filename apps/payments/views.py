from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Bill
from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from payments.models import (
    PaymentSchedule,
    PaymentTransaction,
    ScheduledPayment,
    ScheduledPaymentStatus,
)
from payments.serializers import (
    OwnerPayoutSerializer,
    PaymentScheduleSerializer,
    PaymentTransactionSerializer,
    PayBillSerializer,
    RecordCashSerializer,
    SandboxCompleteSerializer,
    ScheduledPaymentPatchSerializer,
    ScheduledPaymentSerializer,
    ScheduledPaymentWriteSerializer,
)
from payments.services.cash import record_cash
from payments.services.helpers import complete_transaction
from payments.services.pay import pay_bill
from payments.services.payouts import owner_analytics, settle_payout
from payments.services.webhooks import process_webhook


def _serialize_txn(txn):
    return PaymentTransactionSerializer(txn).data


def _serialize_txns(qs):
    return PaymentTransactionSerializer(qs, many=True).data


class PaymentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = PaymentTransaction.objects.filter(user=request.user).order_by('-created_at')
        return Response(api_success(_serialize_txns(qs)))


class ScheduledPaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ScheduledPayment.objects.filter(user=request.user).order_by('scheduled_date')
        data = ScheduledPaymentSerializer(qs, many=True).data
        return Response(api_success(data))

    def post(self, request):
        ser = ScheduledPaymentWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = ser.validated_data

        bill = None
        bill_id = payload.get('billId')
        if bill_id:
            try:
                bill = Bill.objects.get(pk=bill_id, is_deleted=False)
            except Bill.DoesNotExist as exc:
                raise NotFoundError('Bill not found.') from exc

        scheduled = ScheduledPayment.objects.create(
            user=request.user,
            bill=bill,
            bill_name=payload['billName'],
            amount=payload['amount'],
            scheduled_date=payload['scheduledDate'],
            scheduled_time=payload.get('scheduledTime', ''),
            payment_method=payload['paymentMethod'],
            account_number=payload.get('accountNumber', ''),
            reminder_enabled=payload.get('reminderEnabled', True),
            reminder_days=payload.get('reminderDays', []),
            auto_retry=payload.get('autoRetry', False),
            max_retries=payload.get('maxRetries', 0),
            metadata=payload.get('metadata', {}),
        )
        return Response(api_success(ScheduledPaymentSerializer(scheduled).data))


class ScheduledPaymentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_scheduled(self, request, pk) -> ScheduledPayment:
        try:
            scheduled = ScheduledPayment.objects.get(pk=pk, user=request.user)
        except ScheduledPayment.DoesNotExist as exc:
            raise NotFoundError('Scheduled payment not found.') from exc
        return scheduled

    def patch(self, request, pk):
        scheduled = self._get_scheduled(request, pk)
        ser = ScheduledPaymentPatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        field_map = {
            'billName': 'bill_name',
            'amount': 'amount',
            'scheduledDate': 'scheduled_date',
            'scheduledTime': 'scheduled_time',
            'paymentMethod': 'payment_method',
            'accountNumber': 'account_number',
            'reminderEnabled': 'reminder_enabled',
            'reminderDays': 'reminder_days',
            'autoRetry': 'auto_retry',
            'maxRetries': 'max_retries',
            'metadata': 'metadata',
        }
        for camel, snake in field_map.items():
            if camel in ser.validated_data:
                setattr(scheduled, snake, ser.validated_data[camel])
        scheduled.save()
        return Response(api_success(ScheduledPaymentSerializer(scheduled).data))


class ScheduledPaymentCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            scheduled = ScheduledPayment.objects.get(pk=pk, user=request.user)
        except ScheduledPayment.DoesNotExist as exc:
            raise NotFoundError('Scheduled payment not found.') from exc
        scheduled.status = ScheduledPaymentStatus.CANCELLED
        scheduled.save(update_fields=['status', 'updated_at'])
        return Response(api_success(True))


class PaymentSchedulesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = PaymentSchedule.objects.filter(user=request.user).order_by('-created_at')
        data = PaymentScheduleSerializer(qs, many=True).data
        return Response(api_success(data))


class PayBillView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PayBillSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        txn = pay_bill(request.user, ser.validated_data)
        return Response(api_success(_serialize_txn(txn)))


class RecordCashView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can record cash payments.')
        ser = RecordCashSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        txn, payout = record_cash(request.user, ser.validated_data)
        return Response(api_success({
            'transaction': _serialize_txn(txn),
            'payout': OwnerPayoutSerializer(payout).data if payout else None,
        }))


class OwnerPayoutsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can view payouts.')
        from payments.models import OwnerPayout

        qs = OwnerPayout.objects.filter(owner=request.user).order_by('-paid_at', '-created_at')
        data = OwnerPayoutSerializer(qs, many=True).data
        return Response(api_success(data))


class OwnerAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can view payment analytics.')
        return Response(api_success(owner_analytics(request.user)))


class SettlePayoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can settle payouts.')
        payout = settle_payout(request.user, pk)
        return Response(api_success(OwnerPayoutSerializer(payout).data))


class TransactionDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, txn_id):
        try:
            txn = PaymentTransaction.objects.get(transaction_id=txn_id)
        except PaymentTransaction.DoesNotExist as exc:
            raise NotFoundError('Payment transaction not found.') from exc
        return Response(api_success(_serialize_txn(txn)))


class BkashWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        txn = process_webhook('bkash', request)
        return Response(api_success(_serialize_txn(txn) if txn else None))


class NagadWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        txn = process_webhook('nagad', request)
        return Response(api_success(_serialize_txn(txn) if txn else None))


class RocketWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        txn = process_webhook('rocket', request)
        return Response(api_success(_serialize_txn(txn) if txn else None))


class SandboxCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not settings.DEBUG:
            raise ForbiddenError('Sandbox complete is only available in DEBUG mode.')
        ser = SandboxCompleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        txn_id = ser.validated_data['transactionId']
        try:
            txn = PaymentTransaction.objects.get(transaction_id=txn_id)
        except PaymentTransaction.DoesNotExist as exc:
            raise NotFoundError('Payment transaction not found.') from exc
        complete_transaction(txn)
        txn.refresh_from_db()
        return Response(api_success(_serialize_txn(txn)))
