from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from payment_gateway_api.models.request import PostPaymentRequest
from tests.conftest import future_year, valid_payment_payload


def test_valid_request_is_accepted():
    request = PostPaymentRequest(**valid_payment_payload())
    assert request.card_number_last_four() == "8877"


def test_card_number_must_be_numeric():
    with pytest.raises(ValidationError):
        PostPaymentRequest(**valid_payment_payload(card_number="2222abcd43248877"))


@pytest.mark.parametrize("length", [13, 20])
def test_card_number_length_bounds(length):
    with pytest.raises(ValidationError):
        PostPaymentRequest(**valid_payment_payload(card_number="4" * length))


@pytest.mark.parametrize("cvv", ["12", "12345", "12a"])
def test_invalid_cvv_rejected(cvv):
    with pytest.raises(ValidationError):
        PostPaymentRequest(**valid_payment_payload(cvv=cvv))


def test_expiry_in_the_past_is_rejected():
    with pytest.raises(ValidationError, match="past"):
        PostPaymentRequest(**valid_payment_payload(expiry_month=1, expiry_year=2000))


def test_expiry_in_current_month_is_accepted():
    now = datetime.now(timezone.utc)
    request = PostPaymentRequest(**valid_payment_payload(expiry_month=now.month, expiry_year=now.year))
    assert request.expiry_year == now.year


def test_expiry_month_out_of_range_rejected():
    with pytest.raises(ValidationError):
        PostPaymentRequest(**valid_payment_payload(expiry_month=13, expiry_year=future_year()))


def test_amount_must_be_an_integer():
    with pytest.raises(ValidationError):
        PostPaymentRequest(**valid_payment_payload(amount=10.5))


def test_zero_amount_is_accepted_by_gateway_validation():
    request = PostPaymentRequest(**valid_payment_payload(amount=0))
    assert request.amount == 0


def test_currency_must_be_supported():
    with pytest.raises(ValidationError):
        PostPaymentRequest(**valid_payment_payload(currency="JPY"))
