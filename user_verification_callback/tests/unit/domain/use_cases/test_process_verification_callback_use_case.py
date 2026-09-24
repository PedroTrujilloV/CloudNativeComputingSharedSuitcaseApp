"""Unit tests for the process verification callback use case."""

import hashlib

import pytest

from domain.models.updated_user_data import UpdatedUserData
from domain.models.verification_callback import VerificationCallback
from domain.use_cases.process_verification_callback_use_case import (
    ProcessVerificationCallbackUseCase,
)
from errors import (
    EmailNotificationError,
    UserNotFoundError,
    UsersServiceUnavailableError,
)
from tests.conftest import (
    TEST_SECRET_TOKEN,
    FakeEmailNotification,
    FakeUserUpdate,
    sign,
)


def _callback(
    *,
    ruv: str = "base64-ruv",
    user_id: str = "user-1",
    score: int | float = 90.0,
    secret: str = TEST_SECRET_TOKEN,
    verify_token: str | None = None,
) -> VerificationCallback:
    return VerificationCallback(
        RUV=ruv,
        userIdentifier=user_id,
        transactionIdentifier="tx-1",
        createdAt="2026-09-23T12:00:00",
        status="VERIFICADO" if score > 60 else "NO_VERIFICADO",
        score=score,
        verifyToken=(
            verify_token if verify_token is not None else sign(ruv, score, secret)
        ),
    )


def _use_case(
    update: FakeUserUpdate,
    email: FakeEmailNotification | None = None,
    secret: str = TEST_SECRET_TOKEN,
):
    return ProcessVerificationCallbackUseCase(
        user_update=update,
        email_notification=email if email is not None else FakeEmailNotification(),
        secret_token=secret,
    )


@pytest.mark.parametrize("score, expected", [(90.0, "VERIFICADO"), (90, "VERIFICADO")])
def test_valid_signature_above_threshold_is_verificado(score, expected):
    update = FakeUserUpdate()
    email = FakeEmailNotification()

    result = _use_case(update, email).execute(_callback(score=score))

    assert result.applied is True
    assert result.reason == "status_updated"
    assert result.target_status == expected
    assert update.calls == [("user-1", expected)]
    assert result.email_outcome == "sent"
    assert len(email.calls) == 1
    assert email.calls[0].status == expected


@pytest.mark.parametrize(
    "score",
    [60, 60.0, 59.99, 0, 0.0],
)
def test_valid_signature_at_or_below_threshold_is_no_verificado(score):
    update = FakeUserUpdate()
    email = FakeEmailNotification()

    result = _use_case(update, email).execute(_callback(score=score))

    assert result.applied is True
    assert result.reason == "status_updated"
    assert result.target_status == "NO_VERIFICADO"
    assert update.calls == [("user-1", "NO_VERIFICADO")]
    # The email is mandatory for both outcomes.
    assert result.email_outcome == "sent"
    assert len(email.calls) == 1
    assert email.calls[0].status == "NO_VERIFICADO"


def test_just_above_threshold_is_verificado():
    update = FakeUserUpdate()

    result = _use_case(update).execute(_callback(score=60.01))

    assert result.target_status == "VERIFICADO"
    assert update.calls == [("user-1", "VERIFICADO")]


def test_signature_uses_exact_score_text_form():
    """An integer score signs as "90", not "90.0", and still verifies."""
    update = FakeUserUpdate()
    material = f"{TEST_SECRET_TOKEN}:base64-ruv:90"
    token = hashlib.sha256(material.encode("utf-8")).hexdigest()

    result = _use_case(update).execute(_callback(score=90, verify_token=token))

    assert result.applied is True
    assert update.calls == [("user-1", "VERIFICADO")]


def test_invalid_signature_is_rejected_without_change():
    update = FakeUserUpdate()
    email = FakeEmailNotification()

    result = _use_case(update, email).execute(_callback(verify_token="0" * 64))

    assert result.applied is False
    assert result.reason == "signature_mismatch"
    assert result.target_status is None
    assert result.email_outcome is None
    assert update.calls == []
    assert email.calls == []


def test_signature_with_wrong_secret_is_rejected():
    update = FakeUserUpdate()

    result = _use_case(update).execute(_callback(secret="other-secret", score=90.0))

    assert result.applied is False
    assert result.reason == "signature_mismatch"
    assert update.calls == []


def test_tampered_score_is_rejected_without_change():
    update = FakeUserUpdate()
    callback = _callback(score=90.0)
    callback.score = 20.0

    result = _use_case(update).execute(callback)

    assert result.applied is False
    assert result.reason == "signature_mismatch"
    assert update.calls == []


def test_tampered_ruv_is_rejected_without_change():
    update = FakeUserUpdate()
    callback = _callback()
    callback.RUV = "other-ruv"

    result = _use_case(update).execute(callback)

    assert result.applied is False
    assert result.reason == "signature_mismatch"
    assert update.calls == []


def test_non_ascii_verify_token_is_rejected():
    update = FakeUserUpdate()

    result = _use_case(update).execute(_callback(verify_token="señal" * 20))

    assert result.applied is False
    assert result.reason == "signature_mismatch"
    assert update.calls == []


def test_unknown_user_discards_message():
    update = FakeUserUpdate(error=UserNotFoundError("User with id user-1 not found"))
    email = FakeEmailNotification()

    result = _use_case(update, email).execute(_callback())

    assert result.applied is False
    assert result.reason == "user_not_found"
    assert result.target_status == "VERIFICADO"
    assert result.email_outcome is None
    assert update.calls == [("user-1", "VERIFICADO")]
    # No status change was applied, so no email is sent either.
    assert email.calls == []


def test_users_service_error_discards_message():
    update = FakeUserUpdate(error=UsersServiceUnavailableError("unavailable"))
    email = FakeEmailNotification()

    result = _use_case(update, email).execute(_callback())

    assert result.applied is False
    assert result.reason == "users_service_error"
    assert result.target_status == "VERIFICADO"
    assert result.email_outcome is None
    assert email.calls == []


def test_empty_secret_token_still_verifies_signed_messages():
    update = FakeUserUpdate()

    result = _use_case(update, secret="").execute(_callback(secret=""))

    assert result.applied is True
    assert update.calls == [("user-1", "VERIFICADO")]


def test_provider_status_field_is_never_applied():
    """The status carried by TrueNative is ignored; the score decides."""
    update = FakeUserUpdate()
    callback = _callback(score=30.0)
    callback.status = "VERIFICADO"

    result = _use_case(update).execute(callback)

    assert result.target_status == "NO_VERIFICADO"
    assert update.calls == [("user-1", "NO_VERIFICADO")]


def test_email_uses_the_persisted_user_data():
    """The email content comes from the user record the platform persists."""
    persisted = UpdatedUserData(
        id="persisted-id",
        username="persisted_user",
        email="persisted@example.com",
        dni="persisted-dni",
        fullName="Persisted Name",
        phoneNumber="3009999999",
        status="VERIFICADO",
        ruv="persisted-ruv",
    )
    update = FakeUserUpdate(user_data=persisted)
    email = FakeEmailNotification()

    result = _use_case(update, email).execute(
        _callback(ruv="ruv-from-payload", user_id="payload-user")
    )

    assert result.applied is True
    sent = email.calls[0]
    assert sent.user_id == "persisted-id"
    assert sent.status == "VERIFICADO"
    assert sent.ruv == "persisted-ruv"
    assert sent.score == 90.0
    assert sent.username == "persisted_user"
    assert sent.email == "persisted@example.com"
    assert sent.dni == "persisted-dni"
    assert sent.full_name == "Persisted Name"
    assert sent.phone_number == "3009999999"


def test_email_falls_back_to_payload_when_user_block_absent():
    """When the update answer carries no user block, the payload values are used."""
    update = FakeUserUpdate(user_data=UpdatedUserData())
    email = FakeEmailNotification()

    result = _use_case(update, email).execute(
        _callback(ruv="ruv-fallback", user_id="user-fallback", score=45.0)
    )

    assert result.applied is True
    sent = email.calls[0]
    assert sent.user_id == "user-fallback"
    assert sent.status == "NO_VERIFICADO"
    assert sent.ruv == "ruv-fallback"
    assert sent.username is None
    assert sent.email is None
    assert sent.dni is None
    assert sent.full_name is None
    assert sent.phone_number is None


def test_email_failure_keeps_the_applied_status_change():
    """A rejected notification never undoes the persisted status change."""
    update = FakeUserUpdate()
    email = FakeEmailNotification(error=EmailNotificationError("sns refused"))

    result = _use_case(update, email).execute(_callback())

    assert result.applied is True
    assert result.reason == "status_updated"
    assert result.target_status == "VERIFICADO"
    assert update.calls == [("user-1", "VERIFICADO")]
    assert result.email_outcome == "failed"


def test_email_outcome_skipped_when_notification_not_configured():
    update = FakeUserUpdate()
    email = FakeEmailNotification(result=False)

    result = _use_case(update, email).execute(_callback())

    assert result.applied is True
    assert result.email_outcome == "skipped"
