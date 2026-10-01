import asyncio
from uuid import UUID

from payment_gateway_api.domain.models import Payment


class InMemoryPaymentRepository:
    """Simple challenge-appropriate storage abstraction."""

    def __init__(self) -> None:
        self._payments: dict[UUID, Payment] = {}
        self._lock = asyncio.Lock()

    async def add(self, payment: Payment) -> None:
        async with self._lock:
            self._payments[payment.id] = payment

    async def get(self, payment_id: UUID) -> Payment | None:
        async with self._lock:
            return self._payments.get(payment_id)
