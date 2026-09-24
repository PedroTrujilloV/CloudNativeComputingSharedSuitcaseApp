from datetime import datetime, timedelta, timezone

import pytest

from domain.services.card_expiration import (
    expiration_year_and_month,
    is_expired,
    is_valid_expiration_format,
)


def test_the_documented_format_is_valid():
    assert is_valid_expiration_format("28/01")
    assert is_valid_expiration_format("29/12")


def test_the_four_digit_year_variant_is_valid():
    assert is_valid_expiration_format("2028/01")


@pytest.mark.parametrize(
    "value",
    [
        "01/28",  # month first is not the contract
        "28/13",  # impossible month
        "28/0",  # malformed month
        "2801",  # missing separator
        "28/01/2028",  # not a pair
        "",  # empty
        "28-01",  # wrong separator
    ],
)
def test_malformed_values_are_not_valid(value):
    assert is_valid_expiration_format(value) is False


def test_two_digit_years_are_read_from_the_2000_century():
    assert expiration_year_and_month("28/01") == (2028, 1)
    assert expiration_year_and_month("19/01") == (2019, 1)


def test_four_digit_years_are_read_as_is():
    assert expiration_year_and_month("2028/06") == (2028, 6)


def test_malformed_values_raise():
    with pytest.raises(ValueError):
        expiration_year_and_month("01/28")


def test_a_card_in_the_past_is_expired():
    now = datetime.now(timezone.utc)
    year, month = (now.year - 1, now.month)
    assert is_expired(year, month, now) is True


def test_a_card_expiring_in_the_current_month_is_still_valid():
    now = datetime.now(timezone.utc)
    assert is_expired(now.year, now.month, now) is False


def test_a_card_in_the_future_is_not_expired():
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=3650)
    assert is_expired(future.year, future.month, now) is False
