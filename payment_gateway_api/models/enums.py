from enum import Enum


class PaymentStatus(str, Enum):
    AUTHORIZED = "Authorized"
    DECLINED = "Declined"
    REJECTED = "Rejected"  # failed our own validation, never sent to the bank


class Currency(str, Enum):
    GBP = "GBP"
    USD = "USD"
    EUR = "EUR"
