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
    CollectionSettingsSerializer,
    GatewayCredentialSerializer,
    OwnerPayoutSerializer,
    PaymentClaimCreateSerializer,
    PaymentClaimReviewSerializer,
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
from payments.services.claims import (
    create_bill_claim,
    create_mess_claim,
    list_claims_for_owner,
    list_claims_for_user,
    review_claim,
    serialize_claim,
)
from payments.services.collection import (
    assert_owner,
    collection_ledger_analytics,
    collection_report,
    get_collection_settings,
    list_gateway_credentials,
    resolve_payment_instructions,
    update_collection_settings,
    upsert_gateway_credential,
)
from payments.services.helpers import complete_transaction
from payments.services.pay import pay_bill
from payments.services.payouts import settle_payout
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
        return Response(api_success(collection_ledger_analytics(request.user)))


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


class CollectionSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assert_owner(request.user)
        return Response(api_success(get_collection_settings(request.user)))

    def patch(self, request):
        assert_owner(request.user)
        ser = CollectionSettingsSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        return Response(api_success(update_collection_settings(request.user, ser.validated_data)))


class OwnerGatewayCredentialsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assert_owner(request.user)
        return Response(api_success(list_gateway_credentials(request.user)))

    def post(self, request):
        assert_owner(request.user)
        ser = GatewayCredentialSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(api_success(upsert_gateway_credential(request.user, ser.validated_data)))


class PaymentInstructionsView(APIView):
    """Tenant-facing payment instructions for a bill or mess."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        bill_id = request.query_params.get('billId')
        mess_id = request.query_params.get('messId')
        if bill_id:
            try:
                bill = Bill.objects.select_related('owner').get(pk=bill_id, is_deleted=False)
            except Bill.DoesNotExist as exc:
                raise NotFoundError('Bill not found.') from exc
            if (
                bill.tenant_id != request.user.id
                and bill.owner_id != request.user.id
                and request.user.role != 'admin'
            ):
                raise ForbiddenError('Access denied.')
            return Response(
                api_success(resolve_payment_instructions(owner=bill.owner, mess=None))
            )
        if mess_id:
            from mess.models import Mess

            try:
                mess = Mess.objects.select_related('owner').get(pk=mess_id, is_deleted=False)
            except Mess.DoesNotExist as exc:
                raise NotFoundError('Mess not found.') from exc
            return Response(
                api_success(resolve_payment_instructions(owner=mess.owner, mess=mess))
            )
        raise InvalidError('billId or messId is required.')


class PaymentClaimsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get('status')
        if request.user.role in ('owner', 'admin') and request.query_params.get('ownerView') == '1':
            return Response(
                api_success(list_claims_for_owner(request.user, status=status_filter))
            )
        return Response(api_success(list_claims_for_user(request.user)))

    def post(self, request):
        ser = PaymentClaimCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        if data.get('billId'):
            claim = create_bill_claim(request.user, data)
        elif data.get('messId'):
            claim = create_mess_claim(request.user, data)
        else:
            raise InvalidError('billId or messId is required.')
        return Response(api_success(serialize_claim(claim)))


class PaymentClaimReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        assert_owner(request.user)
        ser = PaymentClaimReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        claim = review_claim(
            request.user,
            pk,
            approve=ser.validated_data['approve'],
            reason=ser.validated_data.get('reason', ''),
        )
        return Response(api_success(serialize_claim(claim)))


class CollectionReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assert_owner(request.user)
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        try:
            year_i = int(year) if year else None
            month_i = int(month) if month else None
        except (TypeError, ValueError) as exc:
            raise InvalidError('Invalid year/month.') from exc
        return Response(
            api_success(collection_report(request.user, year=year_i, month=month_i))
        )


class OwnerLedgerView(APIView):
    """Completed receipts for bills owned by this owner (manual ledger)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        assert_owner(request.user)
        qs = (
            PaymentTransaction.objects.filter(
                bill__owner=request.user,
                status='completed',
            )
            .select_related('bill')
            .order_by('-completed_at', '-created_at')[:300]
        )
        return Response(api_success(_serialize_txns(qs)))


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
