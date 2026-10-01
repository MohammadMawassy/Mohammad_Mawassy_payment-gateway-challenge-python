import logging

import httpx
from fastapi.testclient import TestClient

from payment_gateway_api.app import app
from payment_gateway_api.dependencies import get_payment_service
from payment_gateway_api.repositories.payment_repository import InMemoryPaymentRepository
from payment_gateway_api.services.payment_service import PaymentService
from payment_gateway_api.routing.bank_router import BankRouter
from tests.conftest import make_bank_client, valid_payment_payload


def _client_for(handler) -> TestClient:
    transport = httpx.MockTransport(handler)
    service = PaymentService(
        bank_router=BankRouter([make_bank_client(transport)], ["primary"]),
        payment_repository=InMemoryPaymentRepository(),
    )
    app.dependency_overrides[get_payment_service] = lambda: service
    return TestClient(app)


def _authorized(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"authorized": True, "authorization_code": "abc"})


def _declined(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"authorized": False, "authorization_code": ""})


def _bank_down(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, json={})


def test_ping():
    client = _client_for(_authorized)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"app": "payment-gateway-api"}


def test_health_and_readiness_endpoints(client):
    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}


def test_metrics_endpoint_exposes_application_metrics(client):
    client.post("/payments", json=valid_payment_payload())

    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert "http_requests_total" in body
    assert "bank_authorization_total" in body
    assert "payments_total" in body


def test_payment_logs_include_lifecycle_events_and_request_id(client, caplog):
    caplog.set_level(logging.INFO)

    response = client.post(
        "/payments",
        json=valid_payment_payload(),
        headers={"X-Request-ID": "request-for-log-test"},
    )

    assert response.status_code == 201
    messages = [record.getMessage() for record in caplog.records]
    assert any("http_request_started" in message for message in messages)
    assert any("payment_processing_started" in message for message in messages)
    assert any("bank_authorization_started" in message for message in messages)
    assert any("payment_processing_completed" in message for message in messages)
    assert any("http_request_completed" in message for message in messages)
    assert response.headers["X-Request-ID"] == "request-for-log-test"

    combined_messages = " ".join(messages)
    assert valid_payment_payload()["card_number"] not in combined_messages
    assert valid_payment_payload()["cvv"] not in combined_messages


def test_create_and_retrieve_payment():
    client = _client_for(_authorized)
    response = client.post("/payments", json=valid_payment_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "Authorized"
    assert body["card_number_last_four"] == "8877"
    assert "card_number" not in body  # never echo the PAN back
    assert "cvv" not in body
    assert response.headers["Location"] == f"/payments/{body['id']}"

    fetched = client.get(f"/payments/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_declined_payment_returns_201_with_declined_status():
    client = _client_for(_declined)
    response = client.post("/payments", json=valid_payment_payload())
    assert response.status_code == 201
    assert response.json()["status"] == "Declined"


def test_get_unknown_payment_returns_404():
    client = _client_for(_authorized)
    response = client.get("/payments/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"] == "Not Found"


def test_malformed_card_number_returns_400_with_field_errors():
    calls = 0

    def authorized(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _authorized(request)

    client = _client_for(authorized)
    response = client.post("/payments", json=valid_payment_payload(card_number="123"))
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "Rejected"
    assert "card_number" in body["validation_errors"]
    assert calls == 0


def test_missing_field_returns_400():
    payload = valid_payment_payload()
    del payload["cvv"]
    client = _client_for(_authorized)
    response = client.post("/payments", json=payload)
    assert response.status_code == 400
    assert "cvv" in response.json()["validation_errors"]


def test_bank_unavailable_returns_503():
    client = _client_for(_bank_down)
    response = client.post("/payments", json=valid_payment_payload())
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert response.json()["error"] == "Service Unavailable"


def test_bank_request_rejected_returns_502():
    def rejected(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error_message": "bad request"})

    client = _client_for(rejected)
    response = client.post("/payments", json=valid_payment_payload())

    assert response.status_code == 502
    assert response.json()["error"] == "Bad Gateway"


def test_idempotency_key_reuses_payment_without_calling_bank_twice():
    calls = 0

    def authorized_once(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _authorized(request)

    client = _client_for(authorized_once)
    headers = {"Idempotency-Key": "order-123-payment"}
    first = client.post("/payments", json=valid_payment_payload(), headers=headers)
    second = client.post("/payments", json=valid_payment_payload(), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()
    assert calls == 1


def test_idempotency_key_rejects_different_payment_data():
    calls = 0

    def authorized_once(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _authorized(request)

    client = _client_for(authorized_once)
    headers = {"Idempotency-Key": "order-456-payment"}
    first = client.post("/payments", json=valid_payment_payload(), headers=headers)
    conflicting_payload = valid_payment_payload(amount=999)
    second = client.post("/payments", json=conflicting_payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"] == "Conflict"
    assert calls == 1
