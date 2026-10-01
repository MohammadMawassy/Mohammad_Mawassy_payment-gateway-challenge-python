class PaymentGatewayError(Exception):
    """Base for every error this service raises intentionally."""


class PaymentNotFoundError(PaymentGatewayError):
    def __init__(self, payment_id: str) -> None:
        self.payment_id = payment_id
        super().__init__(f"Payment not found: {payment_id}")


class IdempotencyConflictError(PaymentGatewayError):
    """The same idempotency key was reused for different payment data."""


class BankUnavailableError(PaymentGatewayError):
    """The bank could not be reached or returned a 5xx response. The gateway
    cannot confirm an Authorized/Declined outcome for that authorization."""


class BankRequestRejectedError(PaymentGatewayError):
    """The bank explicitly rejected the *shape* of our request. This is a
    bug in our own request-building, not something the end user did --
    surfaced as a 502, never leaked as a 400 back to the merchant."""
