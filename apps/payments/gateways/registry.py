"""Gateway registry — resolve adapter by payment method."""
from payments.gateways.bkash import BkashGateway
from payments.gateways.card import CardGateway
from payments.gateways.cash import CashGateway
from payments.gateways.nagad import NagadGateway
from payments.gateways.rocket import RocketGateway
from payments.models import PaymentMethod

_GATEWAYS = {
    PaymentMethod.BKASH: BkashGateway,
    PaymentMethod.NAGAD: NagadGateway,
    PaymentMethod.ROCKET: RocketGateway,
    PaymentMethod.CASH: CashGateway,
    PaymentMethod.CARD: CardGateway,
}


def get_gateway(method: str):
    cls = _GATEWAYS.get(method)
    if cls is None:
        from core.exceptions import InvalidError

        raise InvalidError(f'Unsupported payment method: {method}')
    return cls()
