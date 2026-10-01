import logging

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from payment_gateway_api.exceptions import (
    BankRequestRejectedError,
    BankUnavailableError,
    IdempotencyConflictError,
    PaymentNotFoundError,
)
from payment_gateway_api.models.response import ErrorResponse
from payment_gateway_api.metrics import validation_failures

logger = logging.getLogger(__name__)


def _error(error: str, message: str, validation_errors: dict[str, str] | None = None) -> dict:
    return jsonable_encoder(ErrorResponse(error=error, message=message, validation_errors=validation_errors))


def register_exception_handlers(app) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        validation_errors: dict[str, str] = {}
        for err in exc.errors():
            loc = err.get("loc", ())
            field = str(loc[-1]) if loc else "body"
            validation_errors[field] = err.get("msg", "Invalid value")
        logger.warning("validation_failed path=%s fields=%s", request.url.path, list(validation_errors))
        validation_failures.labels(request.url.path).inc()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error("Rejected", "Payment request was rejected by the gateway", validation_errors),
        )

    @app.exception_handler(PaymentNotFoundError)
    async def not_found_handler(request: Request, exc: PaymentNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=_error("Not Found", "Payment ID not found"))

    @app.exception_handler(IdempotencyConflictError)
    async def idempotency_conflict_handler(request: Request, exc: IdempotencyConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error("Conflict", str(exc)),
        )

    @app.exception_handler(BankUnavailableError)
    async def bank_unavailable_handler(request: Request, exc: BankUnavailableError) -> JSONResponse:
        logger.warning("bank_unavailable path=%s error_type=%s", request.url.path, type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_error("Service Unavailable", "The acquiring bank is temporarily unavailable. No alternate bank was attempted."),
            headers={"Retry-After": "5"},
        )

    @app.exception_handler(BankRequestRejectedError)
    async def bank_request_rejected_handler(request: Request, exc: BankRequestRejectedError) -> JSONResponse:
        logger.error("bank_rejected_our_request path=%s error_type=%s", request.url.path, type(exc).__name__)
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content=_error("Bad Gateway", "Upstream bank integration error"))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception path=%s", request.url.path)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=_error("Internal Server Error", "An unexpected error occurred"))
