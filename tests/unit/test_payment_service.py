import asyncio

import httpx
import pytest

from payment_gateway_api.routing.bank_router import BankRouter
from payment_gateway_api.clients.bank_client import BankPaymentResponse
from payment_gateway_api.exceptions import PaymentNotFoundError
from payment_gateway_api.models.enums import PaymentStatus
from payment_gateway_api.domain.models import PaymentRequest
from payment_gateway_api.repositories.payment_repository import InMemoryPaymentRepository
from payment_gateway_api.services.payment_service import PaymentService
from tests.conftest import make_bank_client, valid_payment_payload
from payment_gateway_api.models.enums import Currency


def _service(handler) -> PaymentService:
    transport = httpx.MockTransport(handler)
    return PaymentService(
        bank_router=BankRouter([make_bank_client(transport)], ["primary"]),
        payment_repository=InMemoryPaymentRepository(),
    )


def _authorized_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"authorized": True, "authorization_code": "abc"})


async def test_get_payment_not_found_raises():
    service = _service(_authorized_handler)
    with pytest.raises(PaymentNotFoundError):
        await service.get_payment("00000000-0000-0000-0000-000000000000")


async def test_process_then_get_round_trip():
    service = _service(_authorized_handler)
    payload = valid_payment_payload()
    request = PaymentRequest(**{**payload, "currency": Currency.GBP})
    payment = await service.process_payment(request)
    assert payment.status is PaymentStatus.AUTHORIZED

    fetched = await service.get_payment(payment.id)
    assert fetched == payment


async def test_declined_bank_response_stores_declined_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"authorized": False, "authorization_code": ""})

    service = _service(handler)
    payload = valid_payment_payload()
    request = PaymentRequest(**{**payload, "currency": Currency.GBP})
    payment = await service.process_payment(request)
    assert payment.status is PaymentStatus.DECLINED


async def test_two_payments_get_distinct_ids():
    service = _service(_authorized_handler)
    request = PaymentRequest(**{**valid_payment_payload(), "currency": Currency.GBP})
    first = await service.process_payment(request)
    second = await service.process_payment(request)
    assert first.id != second.id


async def test_concurrent_requests_with_same_idempotency_key_call_bank_once():
    class CountingBankClient:
        bank_id = "primary"

        def __init__(self) -> None:
            self.calls = 0

        async def process_payment(self, payment: PaymentRequest) -> BankPaymentResponse:
            self.calls += 1
            await asyncio.sleep(0.01)
            return BankPaymentResponse(authorized=True, authorization_code="abc")

    bank = CountingBankClient()
    service = PaymentService(
        bank_router=BankRouter([bank], ["primary"]),
        payment_repository=InMemoryPaymentRepository(),
    )
    request = PaymentRequest(**{**valid_payment_payload(), "currency": Currency.GBP})

    payments = await asyncio.gather(
        service.process_payment(request, "concurrent-key"),
        service.process_payment(request, "concurrent-key"),
    )

    assert bank.calls == 1
    assert payments[0] == payments[1]
