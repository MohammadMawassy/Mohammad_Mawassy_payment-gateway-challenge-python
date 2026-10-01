import logging

from payment_gateway_api.domain.models import PaymentRequest
from payment_gateway_api.models.enums import Currency
from payment_gateway_api.observability import (
    RequestIdFilter,
    payment_id_context,
    request_id_context,
)


def test_log_filter_adds_request_and_payment_correlation_fields():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="payment_processing_started",
        args=(),
        exc_info=None,
    )
    request_token = request_id_context.set("request-123")
    payment_token = payment_id_context.set("payment-456")

    try:
        assert RequestIdFilter().filter(record)
        assert record.request_id == "request-123"
        assert record.payment_id == "payment-456"
    finally:
        payment_id_context.reset(payment_token)
        request_id_context.reset(request_token)


async def test_payment_context_is_reset_after_an_operation(payment_service):
    from tests.conftest import valid_payment_payload

    payload = valid_payment_payload()
    request = PaymentRequest(**{**payload, "currency": Currency.GBP})
    await payment_service.process_payment(request)
    assert payment_id_context.get() == "-"