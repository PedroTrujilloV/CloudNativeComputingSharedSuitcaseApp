import pytest

from errors import (
    AuthTokenMissingError,
    CardExpiredError,
    CreditCardNotFoundError,
    DuplicateCreditCardError,
    InvalidTokenError,
    TrueNativeRegistrationError,
    UserVerificationUnavailableError,
)


def test_credit_card_not_found_is_an_exception():
    assert issubclass(CreditCardNotFoundError, Exception)


def test_duplicate_credit_card_defaults_to_a_message():
    error = DuplicateCreditCardError()
    assert error.message == "Duplicate credit card"
    assert str(error) == "Duplicate credit card"


def test_duplicate_credit_card_accepts_a_custom_message():
    with pytest.raises(DuplicateCreditCardError):
        raise DuplicateCreditCardError("custom reason")


@pytest.mark.parametrize(
    "error_class, default_message",
    [
        (CardExpiredError, "The card is already expired"),
        (InvalidTokenError, "Invalid or expired token"),
        (AuthTokenMissingError, "Missing bearer token"),
        (
            UserVerificationUnavailableError,
            "User verification service unavailable",
        ),
        (TrueNativeRegistrationError, "TrueNative card registration failed"),
    ],
)
def test_error_vocabulary_defaults_to_a_documented_message(
    error_class, default_message
):
    error = error_class()
    assert error.message == default_message
    assert str(error) == default_message
    assert issubclass(error_class, Exception)


def test_error_vocabulary_accepts_a_custom_message():
    error = TrueNativeRegistrationError("platform on fire")
    assert error.message == "platform on fire"
    assert str(error) == "platform on fire"
