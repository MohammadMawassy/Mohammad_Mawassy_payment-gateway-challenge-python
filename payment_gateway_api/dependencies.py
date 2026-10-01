from functools import lru_cache

import httpx

from payment_gateway_api.routing.bank_router import BankRouter
from payment_gateway_api.clients.factory import build_bank_clients
from payment_gateway_api.config import get_settings
from payment_gateway_api.repositories.payment_repository import InMemoryPaymentRepository
from payment_gateway_api.services.payment_service import PaymentService

_http_client = httpx.AsyncClient()


@lru_cache
def get_payment_repository() -> InMemoryPaymentRepository:
    return InMemoryPaymentRepository()


@lru_cache
def get_bank_router() -> BankRouter:
    settings = get_settings()
    clients = build_bank_clients(settings.banks, _http_client)
    return BankRouter(
        clients,
        bank_ids=settings.routing.bank_ids,
    )


@lru_cache
def get_payment_service() -> PaymentService:
    return PaymentService(
        bank_router=get_bank_router(),
        payment_repository=get_payment_repository(),
    )
