import httpx
import pytest

from payment_gateway_api.api.payments import to_domain
from payment_gateway_api.clients.bank_client import AcquiringBankClient
from payment_gateway_api.exceptions import BankRequestRejectedError, BankUnavailableError
from payment_gateway_api.models.request import PostPaymentRequest
from tests.conftest import valid_payment_payload


def _client_with_handler(handler) -> AcquiringBankClient:
    return AcquiringBankClient(
        bank_id="test-bank",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        base_url="http://bank.test",
        timeout_seconds=1.0,
    )


def _request() -> PostPaymentRequest:
    return PostPaymentRequest(**valid_payment_payload())


async def test_authorized_response_is_mapped_correctly():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"authorized": True, "authorization_code": "abc-123"})

    result = await _client_with_handler(handler).process_payment(to_domain(_request()))
    assert result.authorized is True
    assert result.authorization_code == "abc-123"


async def test_declined_response_has_no_authorization_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"authorized": False, "authorization_code": ""})

    result = await _client_with_handler(handler).process_payment(to_domain(_request()))
    assert result.authorized is False
    assert result.authorization_code is None


async def test_5xx_is_not_retried_and_raises_unavailable():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(503, json={})

    with pytest.raises(BankUnavailableError):
        await _client_with_handler(handler).process_payment(to_domain(_request()))
    assert calls["count"] == 1


async def test_network_timeout_is_not_retried_and_raises_unavailable():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.ConnectTimeout("simulated timeout")

    with pytest.raises(BankUnavailableError):
        await _client_with_handler(handler).process_payment(to_domain(_request()))
    assert calls["count"] == 1


async def test_4xx_is_not_retried_and_raises_rejected():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400, json={"error_message": "bad request"})

    with pytest.raises(BankRequestRejectedError):
        await _client_with_handler(handler).process_payment(to_domain(_request()))
    assert calls["count"] == 1
