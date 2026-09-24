import json
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws

from adapters.messaging import sns_card_result_publisher_adapter
from adapters.messaging.sns_card_result_publisher_adapter import (
    SnsCardResultPublisherAdapter,
)

REGION = "us-east-1"
TOPIC_ARN = (
    f"arn:aws:sns:{REGION}:123456789012:grupo33-card-verification-notifications"
)


class RecordingClient:
    """SNS client stand in: captures the publish call."""

    def __init__(self):
        self.published = []

    def publish(self, **kwargs):
        self.published.append(kwargs)
        return {"MessageId": "00000000-0000-0000-0000-000000000001"}


def test_an_unconfigured_publisher_skips_the_publish(monkeypatch):
    def failing_client():
        raise AssertionError("the client must not be built when the topic is unset")

    monkeypatch.setattr(sns_card_result_publisher_adapter, "get_client", failing_client)
    publisher = SnsCardResultPublisherAdapter(topic_arn="")

    publisher.publish_card_result(
        card_id="card-1",
        status="APROBADA",
        ruv="ruv-1",
        last_four_digits="4242",
        issuer="VISA",
        updated_at="2026-01-01T00:00:00",
        owner_email="owner@example.com",
    )


def test_the_notification_carries_the_stored_card_data_and_the_ruv(monkeypatch):
    client = RecordingClient()
    monkeypatch.setattr(
        sns_card_result_publisher_adapter, "get_client", lambda: client
    )
    publisher = SnsCardResultPublisherAdapter(topic_arn=TOPIC_ARN)

    publisher.publish_card_result(
        card_id="card-1",
        status="RECHAZADA",
        ruv="ruv-1",
        last_four_digits="4242",
        issuer="VISA",
        updated_at="2026-01-01T00:00:00",
        owner_email="owner@example.com",
    )

    assert len(client.published) == 1
    call = client.published[0]
    assert call["TopicArn"] == TOPIC_ARN
    assert call["Subject"] == "Card verification result: RECHAZADA"
    message = json.loads(call["Message"])
    assert message == {
        "eventType": "CARD_RESULT",
        "cardId": "card-1",
        "status": "RECHAZADA",
        "ruv": "ruv-1",
        "lastFourDigits": "4242",
        "issuer": "VISA",
        "updatedAt": "2026-01-01T00:00:00",
        "recipient": "owner@example.com",
    }
    # The raw card number and the CVV never appear in the notification.
    assert "cardNumber" not in message
    assert "cvv" not in message


def test_the_publish_reaches_the_configured_topic():
    # Integration style check against the in memory SNS: the publish must
    # succeed on the topic the adapter targets.
    with mock_aws():
        client = boto3.client("sns", region_name=REGION)
        topic_arn = client.create_topic(
            Name="grupo33-card-verification-notifications"
        )["TopicArn"]
        publisher = SnsCardResultPublisherAdapter(topic_arn=topic_arn)

        publisher.publish_card_result(
            card_id=str(uuid4()),
            status="APROBADA",
            ruv="ruv-1",
            last_four_digits="4242",
            issuer="VISA",
            updated_at="2026-01-01T00:00:00",
            owner_email="owner@example.com",
        )

        topics = client.list_topics()["Topics"]
        assert any(topic["TopicArn"] == topic_arn for topic in topics)


def test_a_publish_failure_is_raised_for_the_redelivery(monkeypatch):
    class FailingClient:
        def publish(self, **_kwargs):
            raise RuntimeError("sns unreachable")

    monkeypatch.setattr(
        sns_card_result_publisher_adapter, "get_client", lambda: FailingClient()
    )
    publisher = SnsCardResultPublisherAdapter(topic_arn=TOPIC_ARN)

    # The failure must propagate so the queue redelivers the event and the
    # mandatory notification is retried.
    with pytest.raises(RuntimeError):
        publisher.publish_card_result(
            card_id="card-1",
            status="APROBADA",
            ruv="ruv-1",
            last_four_digits="4242",
            issuer="VISA",
            updated_at="2026-01-01T00:00:00",
            owner_email="owner@example.com",
        )
