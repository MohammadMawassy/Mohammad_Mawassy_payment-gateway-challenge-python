from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status

from payment_gateway_api.dependencies import get_payment_service
from payment_gateway_api.domain.models import Payment, PaymentRequest
from payment_gateway_api.models.request import PostPaymentRequest
from payment_gateway_api.models.response import PostPaymentResponse
from payment_gateway_api.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


def to_domain(request: PostPaymentRequest) -> PaymentRequest:
    return PaymentRequest(
        card_number=request.card_number,
        expiry_month=request.expiry_month,
        expiry_year=request.expiry_year,
        currency=request.currency,
        amount=request.amount,
        cvv=request.cvv,
    )


def to_response(payment: Payment) -> PostPaymentResponse:
    return PostPaymentResponse(
        id=payment.id,
        status=payment.status,
        card_number_last_four=payment.card_number_last_four,
        expiry_month=payment.expiry_month,
        expiry_year=payment.expiry_year,
        currency=payment.currency,
        amount=payment.amount,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PostPaymentResponse)
async def create_payment(
    request: PostPaymentRequest,
    response: Response,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PostPaymentResponse:
    payment = await payment_service.process_payment(to_domain(request), idempotency_key)
    response.headers["Location"] = f"/payments/{payment.id}"
    return to_response(payment)


@router.get("/{payment_id}", response_model=PostPaymentResponse)
async def get_payment(
    payment_id: UUID,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PostPaymentResponse:
    return to_response(await payment_service.get_payment(payment_id))
