"""Unit tests for the SNS email notification adapter."""

import pytest
from botocore.exceptions import ClientError

from adapters.sns.sns_email_notification import (
    SnsEmailNotification,
    compose_verification_email,
)
from domain.models.verification_email import VerificationEmail
from errors import EmailNotificationError

TOPIC_ARN = "arn:aws:sns:us-east-1:123456789012:user-verification"


class FakeSnsClient:
    """In-memory stand-in for the boto3 SNS client."""

    def __init__(self, error: Exception | None = None):
        self.publish_calls: list[dict] = []
        self.error = error
        self.closed = False

    def publish(self, **kwargs) -> dict:
        if self.error is not None:
            raise self.error
        self.publish_calls.append(kwargs)
        return {"MessageId": "message-1"}

    def close(self) -> None:
        self.closed = True


def _email(**overrides) -> VerificationEmail:
    base = dict(
        user_id="user-1",
        username="test_user",
        email="test_user@example.com",
        dni="12345678",
        full_name="Test User",
        phone_number="3001234567",
        status="VERIFICADO",
        ruv="base64-ruv",
        score=90.0,
    )
    base.update(overrides)
    return VerificationEmail(**base)


def _sns_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "InvalidParameter", "Message": "bad arn"}}, "Publish"
    )


def test_publish_sends_composed_email_to_the_topic():
    fake = FakeSnsClient()
    adapter = SnsEmailNotification(client=fake, topic_arn=TOPIC_ARN)

    sent = adapter.notify_verification_result(_email())

    assert sent is True
    assert len(fake.publish_calls) == 1
    published = fake.publish_calls[0]
    assert published["TargetArn"] == TOPIC_ARN
    assert published["Subject"] == "Identity verification result: VERIFICADO"
    assert "base64-ruv" in published["Message"]


def test_publish_message_contains_the_mandatory_content():
    """Status, RUV and the user data used in the verification are in the body."""
    fake = FakeSnsClient()
    adapter = SnsEmailNotification(client=fake, topic_arn=TOPIC_ARN)

    adapter.notify_verification_result(_email())

    message = fake.publish_calls[0]["Message"]
    assert "Final status: VERIFICADO" in message
    assert "Verification record (RUV): base64-ruv" in message
    assert "Email: test_user@example.com" in message
    assert "DNI: 12345678" in message
    assert "Full name: Test User" in message
    assert "Phone number: 3001234567" in message


def test_publish_message_for_no_verificado_outcome():
    fake = FakeSnsClient()
    adapter = SnsEmailNotification(client=fake, topic_arn=TOPIC_ARN)

    sent = adapter.notify_verification_result(
        _email(status="NO_VERIFICADO", score=45.0)
    )

    assert sent is True
    published = fake.publish_calls[0]
    assert published["Subject"] == "Identity verification result: NO_VERIFICADO"
    assert "could not be verified" in published["Message"]


def test_missing_topic_arn_skips_the_publish():
    """Local runs without the stack output skip the delivery with a notice."""
    fake = FakeSnsClient()
    adapter = SnsEmailNotification(client=fake, topic_arn="")

    sent = adapter.notify_verification_result(_email())

    assert sent is False
    assert fake.publish_calls == []


def test_publish_client_error_raises_email_notification_error():
    fake = FakeSnsClient(error=_sns_error())
    adapter = SnsEmailNotification(client=fake, topic_arn=TOPIC_ARN)

    with pytest.raises(EmailNotificationError):
        adapter.notify_verification_result(_email())


def test_compose_shows_not_provided_for_absent_fields():
    subject, body = compose_verification_email(
        _email(email=None, dni=None, full_name=None, phone_number=None, username=None)
    )

    assert subject == "Identity verification result: VERIFICADO"
    assert "Email: Not provided" in body
    assert "DNI: Not provided" in body
    assert "Full name: Not provided" in body
    assert "Phone number: Not provided" in body
    assert "Hello," in body


def test_compose_includes_user_id_for_traceability():
    _, body = compose_verification_email(_email())

    assert "user-1" in body


def test_default_settings_are_used_when_no_arguments_are_given(monkeypatch):
    monkeypatch.setenv("USER_VERIFICATION_TOPIC_ARN", TOPIC_ARN)
    monkeypatch.setenv("AWS_REGION", "eu-west-1")

    adapter = SnsEmailNotification()

    assert adapter._topic_arn == TOPIC_ARN
    assert adapter._client.meta.region_name == "eu-west-1"
    adapter.close()


def test_endpoint_url_override_reaches_the_boto3_client():
    adapter = SnsEmailNotification(endpoint_url="http://localhost:4566")

    assert adapter._client.meta.endpoint_url.startswith("http://localhost:4566")
    adapter.close()


def test_close_only_closes_owned_clients():
    fake = FakeSnsClient()
    injected = SnsEmailNotification(client=fake, topic_arn=TOPIC_ARN)

    injected.close()

    assert fake.closed is False

    owned = SnsEmailNotification(topic_arn=TOPIC_ARN)
    owned.close()
    assert owned._client is not None
