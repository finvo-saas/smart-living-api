"""Card payment gateway — SSLCommerz / Stripe placeholder."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.exceptions import GatewayTodoError
from payments.gateways.base import PaymentGateway, PaymentIntent


class CardGateway(PaymentGateway):
    prefix = 'CRD'

    def create_payment(
        self,
        *,
        amount: Decimal,
        transaction_id: str,
        account_number: str = '',
        metadata: dict[str, Any] | None = None,
    ) -> PaymentIntent:
        raise GatewayTodoError(
            'Card payments will be available when the payment gateway is connected.',
        )

    def verify_webhook(self, request) -> PaymentIntent | None:
        return None
