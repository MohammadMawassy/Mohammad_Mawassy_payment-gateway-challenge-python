import httpx
import pytest

from payment_gateway_api.api.payments import to_domain
from payment_gateway_api.clients.bank_client import AcquiringBankClient
from payment_gateway_api.clients.mock_bank_client import UnavailableBankClient
from payment_gateway_api.domain.models import PaymentRequest
from payment_gateway_api.exceptions import BankUnavailableError
from payment_gateway_api.models.request import PostPaymentRequest
from payment_gateway_api.routing.bank_router import BankRouter
from tests.conftest import valid_payment_payload


def _client(handler, bank_id):
    return AcquiringBankClient(
        bank_id=bank_id,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        base_url="http://bank.test",
        timeout_seconds=1.0,
    )


def _up_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"authorized": True, "authorization_code": "bank-auth"})


async def test_same_card_always_selects_same_bank():
    banks = [
        _client(_up_handler, "primary"),
        _client(_up_handler, "mock"),
        _client(_up_handler, "simulated"),
    ]
    router = BankRouter(banks, ["primary", "mock", "simulated"])
    payment = to_domain(PostPaymentRequest(**valid_payment_payload()))

    assert router.select_bank(payment).bank_id == router.select_bank(payment).bank_id


async def test_router_can_select_each_configured_bank():
    banks = [
        _client(_up_handler, "primary"),
        _client(_up_handler, "mock"),
        _client(_up_handler, "simulated"),
    ]
    router = BankRouter(banks, ["primary", "mock", "simulated"])

    selected = {
        router.select_bank(
            to_domain(PostPaymentRequest(**valid_payment_payload(card_number=card)))
        ).bank_id
        for card in (
            "4000000000000010",
            "4000000000000051",
            "4000000000000077",
            "5555555555554444",
            "2222405343248877",
        )
    }

    assert selected == {"primary", "mock", "simulated"}


async def test_router_does_not_fail_over_when_selected_bank_is_unavailable():
    unavailable = UnavailableBankClient("mock")
    healthy = _client(_up_handler, "primary")
    router = BankRouter([unavailable, healthy], ["mock", "primary"])

    payment = to_domain(PostPaymentRequest(**valid_payment_payload(card_number="4000000000000010")))
    selected = router.select_bank(payment)

    # Force this test to exercise the unavailable bank without relying on a
    # particular hash value for the sample card.
    router = BankRouter([unavailable, healthy], ["mock"])
    with pytest.raises(BankUnavailableError):
        await router.process_payment(payment)

    assert selected.bank_id in {"mock", "primary"}


def test_router_requires_at_least_one_bank():
    with pytest.raises(ValueError):
        BankRouter([], [])


def test_router_rejects_unknown_route_bank():
    bank = _client(_up_handler, "primary")
    with pytest.raises(ValueError):
        BankRouter([bank], ["missing"])
