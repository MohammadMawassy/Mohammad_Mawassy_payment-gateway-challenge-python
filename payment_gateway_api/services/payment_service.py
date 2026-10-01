import asyncio
import hashlib
import logging
from uuid import UUID, uuid4

from payment_gateway_api.domain.models import Payment, PaymentRequest
from payment_gateway_api.routing.bank_router import BankRouter
from payment_gateway_api.exceptions import IdempotencyConflictError, PaymentNotFoundError
from payment_gateway_api.models.enums import PaymentStatus
from payment_gateway_api.metrics import idempotency_replays, payments
from payment_gateway_api.observability import payment_id_context
from payment_gateway_api.repositories.payment_repository import InMemoryPaymentRepository

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, bank_router: BankRouter, payment_repository: InMemoryPaymentRepository) -> None:
        self._bank_router = bank_router
        self._payment_repository = payment_repository
        # This is intentionally a simple in-memory idempotency implementation
        # for the exercise; production would persist these records in shared storage.
        self._idempotency_records: dict[str, tuple[str, Payment]] = {}
        self._idempotency_locks: dict[str, asyncio.Lock] = {}
        self._idempotency_locks_guard = asyncio.Lock()

    async def get_payment(self, payment_id: UUID) -> Payment:
        payment = await self._payment_repository.get(payment_id)
        if payment is None:
            raise PaymentNotFoundError(str(payment_id))
        return payment

    async def process_payment(self, request: PaymentRequest, idempotency_key: str | None = None) -> Payment:
        if idempotency_key is not None:
            lock = await self._idempotency_lock_for(idempotency_key)
            async with lock:
                return await self._process_idempotent_payment(request, idempotency_key)

        return await self._process_payment(request)

    async def _process_idempotent_payment(self, request: PaymentRequest, idempotency_key: str) -> Payment:
        fingerprint = self._request_fingerprint(request)
        existing = self._idempotency_records.get(idempotency_key)
        if existing is not None:
            existing_fingerprint, payment = existing
            if existing_fingerprint != fingerprint:
                logger.warning("idempotency_conflict")
                raise IdempotencyConflictError(
                    "Idempotency-Key was already used for different payment data"
                )
            logger.info("idempotency_replayed payment_id=%s", payment.id)
            idempotency_replays.inc()
            return payment

        payment = await self._process_payment(request)
        self._idempotency_records[idempotency_key] = (fingerprint, payment)
        return payment

    async def _process_payment(self, request: PaymentRequest) -> Payment:
        payment_id = uuid4()
        token = payment_id_context.set(str(payment_id))
        try:
            logger.info(
                "payment_processing_started amount=%s currency=%s card_last_four=%s",
                request.amount,
                request.currency.value,
                request.card_number_last_four,
            )

            bank_response = await self._bank_router.process_payment(request)
            status = PaymentStatus.AUTHORIZED if bank_response.authorized else PaymentStatus.DECLINED

            payment = Payment(
                id=payment_id,
                status=status,
                card_number_last_four=request.card_number_last_four,
                expiry_month=request.expiry_month,
                expiry_year=request.expiry_year,
                currency=request.currency,
                amount=request.amount,
            )
            await self._payment_repository.add(payment)
            payments.labels(request.currency.value, payment.status.value).inc()

            logger.info(
                "payment_processing_completed status=%s",
                payment.status.value,
            )
            return payment
        finally:
            payment_id_context.reset(token)

    async def _idempotency_lock_for(self, idempotency_key: str) -> asyncio.Lock:
        # Per-key locks make concurrent retries safe without requiring a database.
        async with self._idempotency_locks_guard:
            return self._idempotency_locks.setdefault(idempotency_key, asyncio.Lock())

    @staticmethod
    def _request_fingerprint(request: PaymentRequest) -> str:
        values = (
            request.card_number,
            request.expiry_month,
            request.expiry_year,
            request.currency.value,
            request.amount,
            request.cvv,
        )
        return hashlib.sha256(repr(values).encode("utf-8")).hexdigest()
