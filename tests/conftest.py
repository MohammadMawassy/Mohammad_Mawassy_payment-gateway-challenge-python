from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from payment_gateway_api.app import app
from payment_gateway_api.clients.bank_client import AcquiringBankClient
from payment_gateway_api.dependencies import get_payment_service
from payment_gateway_api.repositories.payment_repository import InMemoryPaymentRepository
from payment_gateway_api.routing.bank_router import BankRouter
from payment_gateway_api.services.payment_service import PaymentService


def future_year() -> int:
    return (datetime.now(timezone.utc) + timedelta(days=365)).year


def valid_payment_payload(**overrides) -> dict:
    payload = {
        "card_number": "2222405343248877",
        "expiry_month": 4,
        "expiry_year": future_year(),
        "currency": "GBP",
        "amount": 100,
        "cvv": "123",
    }
    payload.update(overrides)
    return payload


def make_bank_client(transport: httpx.MockTransport, bank_id: str = "primary") -> AcquiringBankClient:
    return AcquiringBankClient(
        bank_id=bank_id,
        http_client=httpx.AsyncClient(transport=transport),
        base_url="http://bank.test",
        timeout_seconds=1.0,
    )


def make_bank_router(transport: httpx.MockTransport) -> BankRouter:
    return BankRouter([make_bank_client(transport)], ["primary"])


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"authorized": True, "authorization_code": "test-auth-code"})

    return httpx.MockTransport(handler)


@pytest.fixture
def payment_service(mock_transport) -> PaymentService:
    return PaymentService(
        bank_router=make_bank_router(mock_transport),
        payment_repository=InMemoryPaymentRepository(),
    )


@pytest.fixture
def client(payment_service) -> TestClient:
    app.dependency_overrides[get_payment_service] = lambda: payment_service
    with TestClient(app) as test_client:
        yield test_client
