import hashlib
import logging

from payment_gateway_api.clients.base import BankClient, BankPaymentResult
from payment_gateway_api.domain.models import PaymentRequest
from payment_gateway_api.metrics import bank_routing

logger = logging.getLogger(__name__)


class BankRouter:
    """Select exactly one bank using stable card-based distribution.

    The card number is hashed rather than used directly, then mapped to one
    configured bank. This is deterministic, independent of currency, and
    ensures a payment is sent to exactly one bank with no cross-bank failover.
    The router depends on the BankClient contract, so additional bank adapters
    can be introduced without changing payment orchestration.
    """

    def __init__(self, bank_clients: list[BankClient], bank_ids: list[str]) -> None:
        if not bank_clients:
            raise ValueError("BankRouter requires at least one configured bank client")
        if not bank_ids:
            raise ValueError("BankRouter requires at least one configured route")

        self._banks = {client.bank_id: client for client in bank_clients}
        if len(self._banks) != len(bank_clients):
            raise ValueError("Bank IDs must be unique")

        unknown_banks = set(bank_ids) - self._banks.keys()
        if unknown_banks:
            raise ValueError(f"Routes reference unknown bank(s): {sorted(unknown_banks)}")

        self._bank_ids = list(bank_ids)

    def select_bank(self, payment: PaymentRequest) -> BankClient:
        digest = hashlib.sha256(payment.card_number.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % len(self._bank_ids)
        bank = self._banks[self._bank_ids[index]]

        logger.info(
            "bank_selected bank_id=%s routing_rule=stable_card_hash card_last_four=%s",
            bank.bank_id,
            payment.card_number_last_four,
        )
        bank_routing.labels(bank.bank_id).inc()
        return bank

    async def process_payment(self, payment: PaymentRequest) -> BankPaymentResult:
        bank = self.select_bank(payment)
        return await bank.process_payment(payment)
