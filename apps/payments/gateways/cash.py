"""Cash payment gateway — manual / in-person collection."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from payments.gateways.base import PaymentGateway, PaymentIntent


class CashGateway(PaymentGateway):
    prefix = 'CSH'

    def create_payment(
        self,
        *,
        amount: Decimal,
        transaction_id: str,
        account_number: str = '',
        metadata: dict[str, Any] | None = None,
    ) -> PaymentIntent:
        gateway_txn_id = self._generate_txn_id()
        return PaymentIntent(
            gateway_txn_id=gateway_txn_id,
            status='pending',
            raw={'amount': str(amount), 'method': 'Cash'},
        )

    def verify_webhook(self, request) -> PaymentIntent | None:
        return None
