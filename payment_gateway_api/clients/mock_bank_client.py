import logging
import time

from payment_gateway_api.clients.base import BankPaymentResult
from payment_gateway_api.domain.models import PaymentRequest
from payment_gateway_api.exceptions import BankUnavailableError
from payment_gateway_api.metrics import bank_authorization_duration, bank_authorizations

logger = logging.getLogger(__name__)


class UnavailableBankClient:
    """Small bank double used for banks without a supplied simulator.

    It deliberately returns the same gateway-level failure as an unavailable
    upstream bank would produce, without making a network request.
    """

    def __init__(self, bank_id: str) -> None:
        self.bank_id = bank_id

    async def process_payment(self, payment: PaymentRequest) -> BankPaymentResult:
        started = time.perf_counter()
        bank_authorizations.labels(self.bank_id, "unavailable").inc()
        bank_authorization_duration.labels(self.bank_id).observe(time.perf_counter() - started)
        logger.warning(
            "bank_unavailable bank_id=%s reason=no_simulator card_last_four=%s",
            self.bank_id,
            payment.card_number_last_four,
        )
        raise BankUnavailableError(f"[{self.bank_id}] bank unavailable")
