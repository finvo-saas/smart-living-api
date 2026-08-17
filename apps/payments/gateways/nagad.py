"""Nagad merchant gateway adapter."""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

from django.conf import settings

from payments.gateways.base import PaymentGateway, PaymentIntent

logger = logging.getLogger(__name__)


class NagadGateway(PaymentGateway):
    prefix = 'NGD'

    def _has_credentials(self) -> bool:
        return bool(getattr(settings, 'NAGAD_MERCHANT_ID', ''))

    def create_payment(
        self,
        *,
        amount: Decimal,
        transaction_id: str,
        account_number: str = '',
        metadata: dict[str, Any] | None = None,
    ) -> PaymentIntent:
        if not self._has_credentials():
            self._log_sandbox_stub('Nagad')
            gateway_txn_id = self._generate_txn_id()
            status = 'completed' if self._sandbox_auto_complete() else 'processing'
            return PaymentIntent(
                gateway_txn_id=gateway_txn_id,
                status=status,
                raw={'sandbox': True, 'amount': str(amount)},
            )

        gateway_txn_id = self._generate_txn_id()
        # TODO: Real Nagad API integration at NAGAD_BASE_URL
        # Use NAGAD_MERCHANT_ID and NAGAD_MERCHANT_PRIVATE_KEY for signing
        logger.info('Nagad create_payment stub — plug real API at NAGAD_BASE_URL')
        return PaymentIntent(
            gateway_txn_id=gateway_txn_id,
            status='processing',
            redirect_url=self._frontend_redirect(gateway_txn_id),
            raw={'stub': True, 'amount': str(amount), 'invoice': transaction_id},
        )

    def verify_webhook(self, request) -> PaymentIntent | None:
        payload = self._parse_body(request)
        gateway_txn_id = (
            payload.get('issuerPaymentRef')
            or payload.get('paymentRefId')
            or payload.get('trxID')
            or ''
        )
        if not gateway_txn_id:
            return None

        status_raw = (payload.get('status') or payload.get('statusCode') or '').lower()
        if status_raw in ('success', 'completed', '00'):
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
