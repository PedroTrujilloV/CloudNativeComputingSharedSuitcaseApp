"""API tests for the public TrueNative callback endpoint."""

import json

from fastapi.testclient import TestClient

from entrypoints.api.deps import (
    get_email_notification,
    get_process_verification_callback_use_case,
    get_users_service_client,
)
from entrypoints.api.main import app
from errors import (
    EmailNotificationError,
    UserNotFoundError,
    UsersServiceUnavailableError,
)
from tests.conftest import callback_payload


def test_ping_returns_pong(client):
    response = client.get("/users/verify/ping")

    assert response.status_code == 200
    assert response.text == "pong"


def test_well_signed_callback_updates_status_and_notifies(client):
    response = client.patch("/users/verify/callback", json=callback_payload(score=92.5))

    assert response.status_code == 200
    assert client.fake_update.calls == [("user-1", "VERIFICADO")]
    assert len(client.fake_email.calls) == 1
    assert client.fake_email.calls[0].status == "VERIFICADO"


def test_well_signed_callback_updates_status_to_no_verificado(client):
    response = client.patch("/users/verify/callback", json=callback_payload(score=45.0))

    assert response.status_code == 200
    assert client.fake_update.calls == [("user-1", "NO_VERIFICADO")]
    # The email is sent for both outcomes.
    assert len(client.fake_email.calls) == 1
    assert client.fake_email.calls[0].status == "NO_VERIFICADO"


def test_well_signed_callback_with_integer_score(client):
    response = client.patch("/users/verify/callback", json=callback_payload(score=90))

    assert response.status_code == 200
    assert client.fake_update.calls == [("user-1", "VERIFICADO")]
    assert len(client.fake_email.calls) == 1


def test_incorrect_signature_is_rejected_without_change(client):
    payload = callback_payload(score=90.0, verify_token="deadbeef" * 8)

    response = client.patch("/users/verify/callback", json=payload)

    assert response.status_code == 200
    assert client.fake_update.calls == []
    assert client.fake_email.calls == []


def test_tampered_score_is_rejected_without_change(client):
    payload = callback_payload(score=90.0)
    payload["score"] = 20.0

    response = client.patch("/users/verify/callback", json=payload)

    assert response.status_code == 200
    assert client.fake_update.calls == []
    assert client.fake_email.calls == []


def test_unknown_user_answers_200_without_change(client):
    client.fake_update.error = UserNotFoundError("User with id user-1 not found")

    response = client.patch("/users/verify/callback", json=callback_payload())

    assert response.status_code == 200
    assert client.fake_update.calls == [("user-1", "VERIFICADO")]
    assert client.fake_email.calls == []


def test_users_service_error_still_answers_200(client):
    client.fake_update.error = UsersServiceUnavailableError("unavailable")

    response = client.patch("/users/verify/callback", json=callback_payload())

    assert response.status_code == 200
    assert client.fake_email.calls == []


def test_email_failure_still_answers_200(client):
    """A rejected notification never changes the receipt answer."""
    client.fake_email.error = EmailNotificationError("sns refused")

    response = client.patch("/users/verify/callback", json=callback_payload())

    assert response.status_code == 200
    assert client.fake_update.calls == [("user-1", "VERIFICADO")]


def test_callback_ignores_provider_status_field(client):
    payload = callback_payload(score=30.0, status="VERIFICADO")

    response = client.patch("/users/verify/callback", json=payload)

    assert response.status_code == 200
    assert client.fake_update.calls == [("user-1", "NO_VERIFICADO")]
    assert client.fake_email.calls[0].status == "NO_VERIFICADO"


def test_missing_required_field_answers_400(client):
    payload = callback_payload()
    del payload["RUV"]

    response = client.patch("/users/verify/callback", json=payload)

    assert response.status_code == 400
    assert client.fake_update.calls == []
    assert client.fake_email.calls == []


def test_malformed_body_answers_400(client):
    response = client.patch(
        "/users/verify/callback",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert client.fake_update.calls == []
    assert client.fake_email.calls == []


def test_wrong_method_answers_405(client):
    response = client.post("/users/verify/callback", json=callback_payload())

    assert response.status_code == 405
    assert client.fake_update.calls == []
    assert client.fake_email.calls == []


def test_full_wiring_publishes_the_result_email():
    """The complete wiring works end to end with only the AWS clients faked.

    The route uses the real use case, the real Users service client (against
    a mock transport) and the real SNS adapter (against a fake boto3 client),
    so the email content built from the persisted user record is verified.
    """
    import httpx

    from adapters.http.users_service_client import UsersServiceClient
    from adapters.sns.sns_email_notification import SnsEmailNotification

    class FakeSnsClient:
        def __init__(self):
            self.publish_calls = []

        def publish(self, **kwargs):
            self.publish_calls.append(kwargs)

        def close(self):
            pass

    seen = {}
    fake_sns = FakeSnsClient()

    def users_handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(
            200,
            json={
                "msg": "ok",
                "user": {
                    "id": "user-real",
                    "username": "real_user",
                    "email": "real_user@example.com",
                    "dni": "87654321",
                    "fullName": "Real User",
                    "phoneNumber": "3009876543",
                    "status": "VERIFICADO",
                    "ruv": "ruv-real",
                },
            },
        )

    transport_client = httpx.Client(
        base_url="http://users.test", transport=httpx.MockTransport(users_handler)
    )
    sns_topic_arn = "arn:aws:sns:us-east-1:123456789012:user-verification"

    app.dependency_overrides[get_users_service_client] = lambda: UsersServiceClient(
        client=transport_client
    )
    app.dependency_overrides[get_email_notification] = lambda: SnsEmailNotification(
        client=fake_sns, topic_arn=sns_topic_arn
    )
    app.dependency_overrides.pop(get_process_verification_callback_use_case, None)

    try:
        with TestClient(app) as test_client:
            payload = callback_payload(ruv="ruv-real", user_identifier="user-real")
            response = test_client.patch("/users/verify/callback", json=payload)
    finally:
        app.dependency_overrides.clear()
        transport_client.close()

    assert response.status_code == 200

    request = seen["request"]
    assert request.method == "PATCH"
    assert request.url.path == "/users/user-real"
    assert json.loads(request.content) == {"status": "VERIFICADO"}

    assert len(fake_sns.publish_calls) == 1
    published = fake_sns.publish_calls[0]
    assert published["TargetArn"] == sns_topic_arn
    assert published["Subject"] == "Identity verification result: VERIFICADO"
    message = published["Message"]
    assert "Final status: VERIFICADO" in message
    assert "Verification record (RUV): ruv-real" in message
    assert "Email: real_user@example.com" in message
    assert "DNI: 87654321" in message
    assert "Full name: Real User" in message
    assert "Phone number: 3009876543" in message
