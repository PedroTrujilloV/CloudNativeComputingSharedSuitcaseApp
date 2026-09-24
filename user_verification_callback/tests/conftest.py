"""Test helpers for the user verification callback receiver."""

import hashlib

import pytest
from fastapi.testclient import TestClient

from config import Settings
from domain.models.updated_user_data import UpdatedUserData
from domain.models.verification_email import VerificationEmail
from domain.use_cases.process_verification_callback_use_case import (
    ProcessVerificationCallbackUseCase,
)
from entrypoints.api.deps import get_process_verification_callback_use_case
from entrypoints.api.main import app
from errors import EmailNotificationError

# The session wide test environment (pyproject.toml pytest env) provides this
# secret token; the signature helpers sign with it by default.
TEST_SECRET_TOKEN = "test-secret-token"


def sign(ruv: str, score: int | float, secret: str = TEST_SECRET_TOKEN) -> str:
    """Compute the TrueNative verifyToken for a payload."""
    return hashlib.sha256(f"{secret}:{ruv}:{score}".encode("utf-8")).hexdigest()


def callback_payload(
    *,
    ruv: str = "base64-ruv",
    user_identifier: str = "user-1",
    score: int | float = 90.0,
    secret: str = TEST_SECRET_TOKEN,
    verify_token: str | None = None,
    **overrides,
) -> dict:
    """A well formed TrueNative callback body, correctly signed by default."""
    payload = {
        "RUV": ruv,
        "userIdentifier": user_identifier,
        "transactionIdentifier": "tx-1",
        "createdAt": "2026-09-23T12:00:00",
        "status": "VERIFICADO" if score > 60 else "NO_VERIFICADO",
        "score": score,
        "verifyToken": (
            verify_token if verify_token is not None else sign(ruv, score, secret)
        ),
    }
    payload.update(overrides)
    return payload


class FakeUserUpdate:
    """In-memory stand-in for the Users service status update."""

    def __init__(
        self,
        error: Exception | None = None,
        user_data: UpdatedUserData | None = None,
    ):
        self.calls: list[tuple[str, str]] = []
        self.error = error
        self.user_data = (
            user_data
            if user_data is not None
            else UpdatedUserData(
                id="user-1",
                username="test_user",
                email="test_user@example.com",
                dni="12345678",
                fullName="Test User",
                phoneNumber="3001234567",
                status=None,
                ruv=None,
            )
        )

    def update_status(self, user_id: str, status: str) -> UpdatedUserData:
        self.calls.append((user_id, status))
        if self.error is not None:
            raise self.error
        return self.user_data.model_copy(update={"status": status})


class FakeEmailNotification:
    """In-memory stand-in for the email notification port."""

    def __init__(
        self,
        result: bool = True,
        error: Exception | None = None,
    ):
        self.calls: list[VerificationEmail] = []
        self.result = result
        self.error = error

    def notify_verification_result(self, email: VerificationEmail) -> bool:
        self.calls.append(email)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def client():
    """HTTP client with fake Users update and email notification (no real IO)."""
    fake_update = FakeUserUpdate()
    fake_email = FakeEmailNotification()

    app.dependency_overrides[get_process_verification_callback_use_case] = (
        lambda: ProcessVerificationCallbackUseCase(
            user_update=fake_update,
            email_notification=fake_email,
            secret_token=Settings.secret_token,
        )
    )

    with TestClient(app) as test_client:
        test_client.fake_update = fake_update
        test_client.fake_email = fake_email
        yield test_client
    app.dependency_overrides.clear()


__all__ = [
    "TEST_SECRET_TOKEN",
    "sign",
    "callback_payload",
    "FakeUserUpdate",
    "FakeEmailNotification",
    "client",
    "EmailNotificationError",
]
