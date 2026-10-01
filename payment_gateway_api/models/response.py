from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from payment_gateway_api.models.enums import Currency, PaymentStatus


class PostPaymentResponse(BaseModel):
    """The only representation of a payment we ever store or return.
    Deliberately excludes card_number, cvv and full expiry-as-typed -- only
    the last four digits ever leave the validation boundary."""

    id: UUID
    status: PaymentStatus
    card_number_last_four: str
    expiry_month: int
    expiry_year: int
    currency: Currency
    amount: int


class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    validation_errors: Optional[dict[str, str]] = None
