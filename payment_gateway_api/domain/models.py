from dataclasses import dataclass
from uuid import UUID

from payment_gateway_api.models.enums import Currency, PaymentStatus


@dataclass(frozen=True)
class PaymentRequest:
    """Validated payment data used inside the application core."""

    card_number: str
    expiry_month: int
    expiry_year: int
    currency: Currency
    amount: int
    cvv: str

    @property
    def card_number_last_four(self) -> str:
        return self.card_number[-4:]

    @property
    def bank_expiry_date(self) -> str:
        return f"{self.expiry_month:02d}/{self.expiry_year}"


@dataclass(frozen=True)
class Payment:
    """Payment representation owned by the domain, not by FastAPI/Pydantic."""

    id: UUID
    status: PaymentStatus
    card_number_last_four: str
    expiry_month: int
    expiry_year: int
    currency: Currency
    amount: int
