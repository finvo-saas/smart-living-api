"""bKash tokenized checkout gateway adapter."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from decimal import Decimal
from typing import Any

from django.conf import settings

from core.exceptions import InvalidError
from payments.gateways.base import PaymentGateway, PaymentIntent

logger = logging.getLogger(__name__)


class BkashGateway(PaymentGateway):
    prefix = 'BKS'

    def _has_credentials(self) -> bool:
        return bool(
            getattr(settings, 'BKASH_APP_KEY', '')
            and getattr(settings, 'BKASH_APP_SECRET', '')
        )

    def create_payment(
        self,
        *,
        amount: Decimal,
        transaction_id: str,
        account_number: str = '',
        metadata: dict[str, Any] | None = None,
    ) -> PaymentIntent:
        if not self._has_credentials():
            self._log_sandbox_stub('bKash')
            gateway_txn_id = self._generate_txn_id()
            status = 'completed' if self._sandbox_auto_complete() else 'processing'
            return PaymentIntent(
                gateway_txn_id=gateway_txn_id,
                status=status,
                raw={'sandbox': True, 'amount': str(amount), 'account': account_number},
            )

        gateway_txn_id = self._generate_txn_id()
        # TODO(M1): Live bKash/Nagad settlement for mess dues — intentionally deferred.
        # Wire PaymentIntent here after merchant credentials; UI shows dues only for now.
        logger.info('bKash create_payment stub — plug real API at BKASH_BASE_URL')
        return PaymentIntent(
            gateway_txn_id=gateway_txn_id,
            status='processing',
            redirect_url=self._frontend_redirect(gateway_txn_id),
            raw={'stub': True, 'amount': str(amount), 'invoice': transaction_id},
        )

    def verify_webhook(self, request) -> PaymentIntent | None:
        payload = self._parse_body(request)
        if not payload:
            return None

        secret = getattr(settings, 'BKASH_WEBHOOK_SECRET', '')
        if secret:
            signature = request.headers.get('X-Signature', '')
            if not self._verify_signature(request.body, signature, secret):
                raise InvalidError('Invalid webhook signature.')

        gateway_txn_id = (
            payload.get('trxID')
            or payload.get('paymentID')
            or payload.get('transaction_id')
            or ''
        )
        if not gateway_txn_id:
            return None

        status_raw = (payload.get('transactionStatus') or payload.get('status') or '').lower()
        if status_raw in ('completed', 'success', 'successful'):
            status = 'completed'
        elif status_raw in ('failed', 'failure', 'cancelled'):
            status = 'failed'
        else:
            status = 'processing'

        return PaymentIntent(
            gateway_txn_id=gateway_txn_id,
            status=status,
            raw=payload,
        )

    def _parse_body(self, request) -> dict:
        try:
            if hasattr(request, 'data') and request.data:
                return dict(request.data)
            return json.loads(request.body.decode('utf-8') or '{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _verify_signature(self, body: bytes, signature: str, secret: str) -> bool:
        if not signature:
            return False
        expected = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
