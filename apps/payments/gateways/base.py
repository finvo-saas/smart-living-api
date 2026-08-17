"""Payment gateway protocol and shared types."""
from __future__ import annotations

import logging
import random
import string
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class PaymentIntent:
    gateway_txn_id: str
    status: str  # processing | completed | pending | failed
    redirect_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentGateway(ABC):
    """Abstract payment gateway adapter."""

    prefix: str = 'TXN'

    @abstractmethod
    def create_payment(
        self,
        *,
        amount: Decimal,
        transaction_id: str,
        account_number: str = '',
        metadata: dict[str, Any] | None = None,
    ) -> PaymentIntent:
        ...

    @abstractmethod
    def verify_webhook(self, request) -> PaymentIntent | None:
        ...

    def _generate_txn_id(self) -> str:
        suffix = ''.join(random.choices(string.digits, k=5))
        return f'{self.prefix}-{int(time.time())}-{suffix}'

    def _sandbox_auto_complete(self) -> bool:
        return getattr(settings, 'PAYMENT_SANDBOX_AUTO_COMPLETE', True)

    def _frontend_redirect(self, gateway_txn_id: str) -> str:
        frontend = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return f'{frontend.rstrip("/")}/payments/result?txn={gateway_txn_id}'

    def _log_sandbox_stub(self, gateway_name: str) -> None:
        logger.warning(
            'SANDBOX stub — replace credentials in .env (%s gateway)',
            gateway_name,
        )
