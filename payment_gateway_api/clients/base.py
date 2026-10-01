from typing import Protocol

from payment_gateway_api.domain.models import PaymentRequest


class BankPaymentResult(Protocol):
    authorized: bool
    authorization_code: str | None


class BankClient(Protocol):
    """Contract implemented by each acquiring-bank adapter."""

    bank_id: str

    async def process_payment(self, payment: PaymentRequest) -> BankPaymentResult: ...
