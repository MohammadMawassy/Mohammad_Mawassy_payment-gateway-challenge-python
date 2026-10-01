"""
Runs against the *real* bank simulator started by `docker-compose up`,
using the documented test card numbers from imposters/bank_simulator.ejs:

  - card ending in 1/3/5/7/9 -> 200, authorized: true
  - card ending in 2/4/6/8   -> 200, authorized: false
  - card ending in 0         -> 503 (simulates the bank being down)

Everything else in the test suite mocks the bank at the HTTP boundary for
speed and determinism. This file is the one place that talks to the actual
simulator, so a change to its contract (or our client's assumptions about
it) gets caught even though it's skipped in normal/CI-without-docker runs.
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from payment_gateway_api.app import app
from tests.conftest import valid_payment_payload

BANK_URL = "http://localhost:8080"


def _bank_simulator_reachable() -> bool:
    try:
        response = httpx.post(
            f"{BANK_URL}/payments",
            json={
                "card_number": "4000000000000051",
                "expiry_date": "04/2030",
                "currency": "GBP",
                "amount": 100,
                "cvv": "123",
            },
            timeout=0.5,
        )
        return response.status_code in {200, 503}
    except httpx.HTTPError:
        return False
    except Exception:
        return False


requires_live_bank = pytest.mark.skipif(
    not _bank_simulator_reachable(),
    reason="bank simulator not running -- start it with `docker-compose up -d`",
)


@pytest.fixture(scope="module")
def live_client():
    with TestClient(app) as test_client:
        yield test_client


CARD_ENDING = {0: '4000000000000010', 1: '4000000000000291', 2: '4000000000000382', 7: '4000000000000127', 8: '4000000000000028'}

@requires_live_bank
def test_card_ending_in_odd_digit_is_authorized(live_client):
    response = live_client.post("/payments", json=valid_payment_payload(card_number=CARD_ENDING[1]))
    assert response.status_code == 201
    assert response.json()["status"] == "Authorized"


@requires_live_bank
def test_card_ending_in_even_digit_is_declined(live_client):
    response = live_client.post("/payments", json=valid_payment_payload(card_number=CARD_ENDING[2]))
    assert response.status_code == 201
    assert response.json()["status"] == "Declined"


@requires_live_bank
def test_card_ending_in_zero_triggers_bank_unavailable(live_client):
    response = live_client.post("/payments", json=valid_payment_payload(card_number=CARD_ENDING[0]))
    assert response.status_code == 503
