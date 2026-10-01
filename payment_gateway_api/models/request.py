from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

from payment_gateway_api.models.enums import Currency


class PostPaymentRequest(BaseModel):
    card_number: str = Field(
        ...,
        min_length=14,
        max_length=19,
        description="14-19 digit PAN, numeric only",
    )
    expiry_month: int = Field(..., ge=1, le=12)
    expiry_year: int = Field(..., ge=1000, le=9999)
    currency: Currency
    amount: int = Field(..., strict=True, description="Amount in the currency's minor unit (e.g. pence)")
    cvv: str = Field(..., description="3-4 digit card verification value")

    @field_validator("card_number")
    @classmethod
    def validate_card_number(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("card_number must contain only digits")
        return v

    @field_validator("cvv")
    @classmethod
    def validate_cvv(cls, v: str) -> str:
        if not v.isdigit() or not (3 <= len(v) <= 4):
            raise ValueError("cvv must be 3 or 4 digits")
        return v

    @model_validator(mode="after")
    def validate_expiry_not_in_past(self) -> "PostPaymentRequest":
        now = datetime.now(timezone.utc)
        # Card is valid through the END of its expiry month.
        if (self.expiry_year, self.expiry_month) < (now.year, now.month):
            raise ValueError("card expiry_month/expiry_year is in the past")
        return self

    def card_number_last_four(self) -> str:
        return self.card_number[-4:]

    def bank_expiry_date(self) -> str:
        return f"{self.expiry_month:02d}/{self.expiry_year}"
