from errors import (
    CardNotFoundError,
    CardVerificationEventError,
    CardVerificationPendingError,
    TrueNativePollingError,
)


def test_the_event_error_keeps_a_custom_message():
    error = CardVerificationEventError("bad record")
    assert error.message == "bad record"
    assert str(error) == "bad record"


def test_the_event_error_has_a_default_message():
    error = CardVerificationEventError()
    assert error.message == "Invalid card verification event"


def test_the_not_found_error_keeps_a_custom_message():
    error = CardNotFoundError("card 123 missing")
    assert error.message == "card 123 missing"


def test_the_not_found_error_has_a_default_message():
    error = CardNotFoundError()
    assert error.message == "Card not found"


def test_the_polling_error_keeps_a_custom_message():
    error = TrueNativePollingError("TrueNative answered with status 500")
    assert error.message == "TrueNative answered with status 500"


def test_the_polling_error_has_a_default_message():
    error = TrueNativePollingError()
    assert error.message == "TrueNative polling request failed"


def test_the_pending_error_keeps_a_custom_message():
    error = CardVerificationPendingError("card 123 still pending")
    assert error.message == "card 123 still pending"


def test_the_pending_error_has_a_default_message():
    error = CardVerificationPendingError()
    assert error.message == "No terminal card state within the bounded attempts"
