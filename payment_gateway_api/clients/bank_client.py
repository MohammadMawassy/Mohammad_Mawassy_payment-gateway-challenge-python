import logging
import time

import httpx
from pydantic import BaseModel, field_validator

from payment_gateway_api.domain.models import PaymentRequest
from payment_gateway_api.exceptions import BankRequestRejectedError, BankUnavailableError
from payment_gateway_api.metrics import bank_authorization_duration, bank_authorizations

logger = logging.getLogger(__name__)


class BankPaymentResponse(BaseModel):
    authorized: bool
    authorization_code: str | None = None

    @field_validator("authorization_code", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        return None if value == "" else value


class AcquiringBankClient:
    """HTTP adapter for a real acquiring-bank endpoint.

    There is intentionally no retry or circuit-breaker layer here. A bank
    timeout/network error or 5xx is surfaced as unavailable immediately.
    """

    def __init__(
        self,
        bank_id: str,
        http_client: httpx.AsyncClient,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.bank_id = bank_id
        self._http_client = http_client
        self._payments_url = f"{base_url.rstrip('/')}/payments"
        self._timeout_seconds = timeout_seconds

    async def process_payment(self, payment: PaymentRequest) -> BankPaymentResponse:
        payload = self._build_payload(payment)
        started = time.perf_counter()

        logger.info(
            "bank_authorization_started bank_id=%s card_last_four=%s",
            self.bank_id,
            payment.card_number_last_four,
        )

        try:
            response = await self._http_client.post(
                self._payments_url,
                json=payload,
                timeout=self._timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            self._record_authorization("unavailable", started)
            logger.warning(
                "bank_unavailable bank_id=%s error_type=%s",
                self.bank_id,
                type(exc).__name__,
            )
            raise BankUnavailableError(f"[{self.bank_id}] bank unavailable") from exc

        try:
            self._raise_for_bank_status(response)
            result = self._parse_response(response)
        except BankUnavailableError:
            self._record_authorization("unavailable", started)
            raise
        except BankRequestRejectedError:
            self._record_authorization("rejected", started)
            raise

        self._record_authorization("authorized" if result.authorized else "declined", started)

        logger.info(
            "bank_authorization_completed bank_id=%s authorized=%s",
            self.bank_id,
            result.authorized,
        )
        return result

    def _record_authorization(self, outcome: str, started: float) -> None:
        bank_authorizations.labels(self.bank_id, outcome).inc()
        bank_authorization_duration.labels(self.bank_id).observe(time.perf_counter() - started)

    @staticmethod
    def _build_payload(payment: PaymentRequest) -> dict[str, object]:
        return {
            "card_number": payment.card_number,
            "expiry_date": payment.bank_expiry_date,
            "currency": payment.currency.value,
            "amount": payment.amount,
            "cvv": payment.cvv,
        }

    def _raise_for_bank_status(self, response: httpx.Response) -> None:
        if 500 <= response.status_code < 600:
            logger.warning(
                "bank_unavailable bank_id=%s status=%s",
                self.bank_id,
                response.status_code,
            )
            raise BankUnavailableError(f"[{self.bank_id}] bank unavailable")

        if 400 <= response.status_code < 500:
            logger.warning(
                "bank_request_rejected bank_id=%s status=%s",
                self.bank_id,
                response.status_code,
            )
            raise BankRequestRejectedError("bank rejected the request")

    def _parse_response(self, response: httpx.Response) -> BankPaymentResponse:
        try:
            return BankPaymentResponse(**response.json())
        except (ValueError, TypeError) as exc:
            raise BankUnavailableError(f"[{self.bank_id}] invalid bank response") from exc
