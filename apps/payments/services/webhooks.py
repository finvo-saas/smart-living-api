"""Gateway webhook processing."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core.exceptions import InvalidError, NotFoundError
from payments.gateways.registry import get_gateway
from payments.models import (
    PaymentGateway,
    PaymentTransaction,
    PaymentTransactionStatus,
    PaymentWebhookEvent,
)
from payments.services.helpers import complete_transaction

_GATEWAY_METHOD = {
    PaymentGateway.BKASH: 'bKash',
    PaymentGateway.NAGAD: 'Nagad',
    PaymentGateway.ROCKET: 'Rocket',
}


def _gateway_event_id(gateway: str, payload: dict, intent_txn_id: str) -> str:
    return (
        payload.get('event_id')
        or payload.get('eventId')
        or payload.get('paymentID')
        or payload.get('issuerPaymentRef')
        or f'{gateway}:{intent_txn_id}'
    )


@transaction.atomic
def process_webhook(gateway: str, request) -> PaymentTransaction | None:
    if gateway not in PaymentGateway.values:
        raise InvalidError(f'Unknown gateway: {gateway}')

    method = _GATEWAY_METHOD.get(gateway, gateway)
    adapter = get_gateway(method)
    intent = adapter.verify_webhook(request)
    if intent is None:
        raise InvalidError('Could not parse webhook payload.')

    event_id = _gateway_event_id(gateway, intent.raw, intent.gateway_txn_id)
    existing_event = PaymentWebhookEvent.objects.filter(gateway_event_id=event_id).first()
    if existing_event and existing_event.processed:
        return existing_event.payment_transaction

    webhook_event, _ = PaymentWebhookEvent.objects.get_or_create(
        gateway_event_id=event_id,
        defaults={
            'gateway': gateway,
            'raw_payload': intent.raw,
        },
    )

    try:
        txn = PaymentTransaction.objects.select_for_update().get(
            transaction_id=intent.gateway_txn_id,
        )
    except PaymentTransaction.DoesNotExist as exc:
        raise NotFoundError('Payment transaction not found.') from exc

    webhook_event.payment_transaction = txn
    webhook_event.raw_payload = intent.raw
    webhook_event.save(update_fields=['payment_transaction', 'raw_payload', 'updated_at'])

    if intent.status == PaymentTransactionStatus.COMPLETED:
        complete_transaction(txn)
    elif intent.status == PaymentTransactionStatus.FAILED:
        txn.status = PaymentTransactionStatus.FAILED
        txn.failure_reason = intent.raw.get('errorMessage') or intent.raw.get('message') or 'Payment failed'
        txn.save(update_fields=['status', 'failure_reason', 'updated_at'])
    else:
        txn.status = PaymentTransactionStatus.PROCESSING
        txn.gateway_payload = intent.raw
        txn.save(update_fields=['status', 'gateway_payload', 'updated_at'])

    webhook_event.processed = True
    webhook_event.processed_at = timezone.now()
    webhook_event.save(update_fields=['processed', 'processed_at', 'updated_at'])

    return txn
