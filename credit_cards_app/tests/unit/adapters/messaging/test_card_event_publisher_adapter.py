import json

import boto3
import pytest
from moto import mock_aws

from adapters.messaging import card_event_publisher_adapter
from adapters.messaging.card_event_publisher_adapter import (
    SqsCardEventPublisherAdapter,
)

REGION = "us-east-1"


@pytest.fixture
def sqs():
    """In memory SQS with a verification queue."""
    with mock_aws():
        client = boto3.client("sqs", region_name=REGION)
        queue_url = client.create_queue(
            QueueName="card-verification-queue"
        )["QueueUrl"]
        yield client, queue_url


def test_an_unconfigured_publisher_skips_the_publish(monkeypatch):
    def failing_client():
        raise AssertionError("the client must not be built when the queue is unset")

    monkeypatch.setattr(card_event_publisher_adapter, "get_client", failing_client)
    publisher = SqsCardEventPublisherAdapter(queue_url="")

    publisher.publish_verification_event(
        card_id="card-1",
        ruv="ruv-1",
        user_id="user-1",
        owner_email="owner@example.com",
        last_four_digits="4242",
        issuer="VISA",
        status="POR_VERIFICAR",
        created_at="2026-01-01T00:00:00",
    )


def test_the_event_is_published_with_the_stored_card_data(sqs):
    client, queue_url = sqs
    publisher = SqsCardEventPublisherAdapter(queue_url=queue_url)

    publisher.publish_verification_event(
        card_id="card-1",
        ruv="ruv-1",
        user_id="user-1",
        owner_email="owner@example.com",
        last_four_digits="4242",
        issuer="VISA",
        status="POR_VERIFICAR",
        created_at="2026-01-01T00:00:00",
    )

    messages = client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
    assert len(messages["Messages"]) == 1
    event = json.loads(messages["Messages"][0]["Body"])
    assert event["eventType"] == "CARD_VERIFICATION_REQUESTED"
    assert event["cardId"] == "card-1"
    assert event["ruv"] == "ruv-1"
    assert event["userId"] == "user-1"
    assert event["ownerEmail"] == "owner@example.com"
    assert event["lastFourDigits"] == "4242"
    assert event["issuer"] == "VISA"
    assert event["status"] == "POR_VERIFICAR"
    assert event["createdAt"] == "2026-01-01T00:00:00"


def test_a_publish_failure_is_logged_and_not_raised(monkeypatch, caplog):
    class FailingClient:
        def send_message(self, **_kwargs):
            raise RuntimeError("queue unreachable")

    monkeypatch.setattr(
        card_event_publisher_adapter, "get_client", lambda: FailingClient()
    )
    publisher = SqsCardEventPublisherAdapter(queue_url="http://sqs.test/queue")

    with caplog.at_level("ERROR"):
        publisher.publish_verification_event(
            card_id="card-1",
            ruv="ruv-1",
            user_id="user-1",
            owner_email="owner@example.com",
            last_four_digits="4242",
            issuer="VISA",
            status="POR_VERIFICAR",
            created_at="2026-01-01T00:00:00",
        )

    assert any(
        "Failed to publish the verification event" in record.message
        for record in caplog.records
    )
