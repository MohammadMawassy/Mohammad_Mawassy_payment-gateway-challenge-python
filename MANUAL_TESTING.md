# Manual API Testing

This document contains curl and Postman checks for the payment gateway.

## Start the services

From the repository root:

```bash
docker-compose up -d
poetry run python main.py
```

The gateway runs at `http://localhost:8000`.
The bank simulator runs at `http://localhost:8080`.

The default router uses a stable SHA-256 hash of the card number to select one
of these banks:

| Card number | Selected bank | Result |
| --- | --- | --- |
| `1000000000000001` | `primary` | Authorized |
| `1000000000000002` | `primary` | Declined |
| `1000000000000010` | `primary` | Bank unavailable |
| `1000000000000004` | `mock` | Bank unavailable |
| `1000000000000000` | `simulated` | Bank unavailable |

These are test card numbers. The application does not perform a Luhn check.

All payment requests below use this valid payload unless otherwise stated:

```json
{
  "card_number": "1000000000000001",
  "expiry_month": 12,
  "expiry_year": 2027,
  "currency": "GBP",
  "amount": 100,
  "cvv": "123"
}
```

## Gateway endpoints

### 1. Root endpoint

```bash
curl -i http://localhost:8000/
```

Expected: `200 OK`

```json
{"app":"payment-gateway-api"}
```

### 2. Health endpoint

```bash
curl -i http://localhost:8000/health
```

Expected: `200 OK`

```json
{"status":"ok"}
```

### 3. Readiness endpoint

```bash
curl -i http://localhost:8000/ready
```

Expected: `200 OK`

```json
{"status":"ready"}
```

### 4. Prometheus metrics

```bash
curl -i http://localhost:8000/metrics
```

Expected: `200 OK` and text containing metrics such as:

```text
http_requests_total
http_request_duration_seconds
bank_authorization_total
bank_authorization_duration_seconds
payments_total
payment_validation_failures_total
payment_idempotency_replays_total
bank_routing_total
```

## Payment processing

### 5. Authorized payment

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `201 Created`, a `Location` header, and a response similar to:

```json
{
  "id": "<uuid>",
  "status": "Authorized",
  "card_number_last_four": "0001",
  "expiry_month": 12,
  "expiry_year": 2027,
  "currency": "GBP",
  "amount": 100
}
```

The response must not contain `card_number` or `cvv`.
Save the returned `id` for the retrieval test.

### 6. Declined payment

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000002",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `201 Created` with:

```json
{"status":"Declined"}
```

### 7. Primary bank unavailable

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000010",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `503 Service Unavailable`, `Retry-After: 5`, and:

```json
{
  "error": "Service Unavailable",
  "message": "The acquiring bank is temporarily unavailable. No alternate bank was attempted.",
  "timestamp": "<timestamp>"
}
```

### 8. Mock bank unavailable

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000004",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `503 Service Unavailable`. The gateway must not try another bank.

### 9. Simulated bank unavailable

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000000",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `503 Service Unavailable`.

## Payment retrieval

### 10. Retrieve a payment

Replace `<payment-id>` with the ID returned by the authorized payment test.

```bash
curl -i http://localhost:8000/payments/<payment-id>
```

Expected: `200 OK` and the same payment body returned during creation.

### 11. Retrieve an unknown payment

```bash
curl -i http://localhost:8000/payments/00000000-0000-0000-0000-000000000000
```

Expected: `404 Not Found`

```json
{
  "error": "Not Found",
  "message": "Payment ID not found",
  "timestamp": "<timestamp>"
}
```

## Validation and Rejected responses

Invalid gateway input must return `400 Bad Request`, contain
`"error": "Rejected"`, and must not call the bank.

### 12. Card number too short

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "123",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `400 Bad Request` with a `card_number` validation error.

### 13. Card number contains letters

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "10000000000000AB",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `400 Bad Request` with `"error": "Rejected"`.

### 14. Invalid CVV

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "12"
  }'
```

Expected: `400 Bad Request` with a `cvv` validation error.

### 15. Missing required field

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100
  }'
```

Expected: `400 Bad Request` with a `cvv` validation error.

### 16. Unsupported currency

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "JPY",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `400 Bad Request` with `"error": "Rejected"`.
Supported currencies are `GBP`, `USD`, and `EUR`.

### 17. Expired card

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 1,
    "expiry_year": 2020,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `400 Bad Request`.

### 18. Invalid expiry month

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 13,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `400 Bad Request`.

### 19. Non-integer amount

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 10.5,
    "cvv": "123"
  }'
```

Expected: `400 Bad Request`.

## Idempotency

### 20. Idempotency replay

Run this command twice:

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-123-payment" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected:

- Both responses are `201 Created`.
- Both responses contain the same payment ID.
- The bank is called only once.

### 21. Idempotency conflict

First run:

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-456-payment" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Then reuse the same key with a different amount:

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-456-payment" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 999,
    "cvv": "123"
  }'
```

Expected: `409 Conflict`

```json
{
  "error": "Conflict",
  "message": "Idempotency-Key was already used for different payment data",
  "timestamp": "<timestamp>"
}
```

### 22. Concurrent idempotency requests

```bash
curl -s -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: concurrent-payment" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }' &

curl -s -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: concurrent-payment" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }' &

wait
```

Expected: both responses contain the same payment ID and only one bank
authorization occurs.

## Request correlation and security

### 23. Supplied request ID

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: manual-test-123" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected response header:

```text
X-Request-ID: manual-test-123
```

Check the application logs. The request ID and payment ID should appear in the
request, payment, routing, bank, and completion log events.

### 24. Generated request ID

Run the same payment request without `X-Request-ID`:

```bash
curl -i -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_month": 12,
    "expiry_year": 2027,
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: the response contains a generated `X-Request-ID` header.

Check that the response and logs never expose the full card number or CVV.

## Direct bank simulator checks

These requests test the simulator independently of the gateway.

### 25. Simulator authorization

```bash
curl -i -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000001",
    "expiry_date": "12/2027",
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `200 OK` with `authorized: true` and an authorization code.

### 26. Simulator decline

```bash
curl -i -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000002",
    "expiry_date": "12/2027",
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `200 OK` with:

```json
{"authorized":false,"authorization_code":""}
```

### 27. Simulator unavailable

```bash
curl -i -X POST http://localhost:8080/payments \
  -H "Content-Type: application/json" \
  -d '{
    "card_number": "1000000000000010",
    "expiry_date": "12/2027",
    "currency": "GBP",
    "amount": 100,
    "cvv": "123"
  }'
```

Expected: `503 Service Unavailable`.

## Postman setup

Create a Postman environment with:

```text
baseUrl   = http://localhost:8000
paymentId =
```

Create these requests:

| Method | URL |
| --- | --- |
| GET | `{{baseUrl}}/` |
| GET | `{{baseUrl}}/health` |
| GET | `{{baseUrl}}/ready` |
| GET | `{{baseUrl}}/metrics` |
| POST | `{{baseUrl}}/payments` |
| GET | `{{baseUrl}}/payments/{{paymentId}}` |

For `POST /payments`, use the valid JSON payload from the beginning of this
document and add:

```text
Content-Type: application/json
```

For idempotency testing, add:

```text
Idempotency-Key: order-123-payment
```

For request correlation testing, add:

```text
X-Request-ID: postman-test-123
```

After creating a payment, copy the returned `id` into the `paymentId`
environment variable and run the retrieval request.
