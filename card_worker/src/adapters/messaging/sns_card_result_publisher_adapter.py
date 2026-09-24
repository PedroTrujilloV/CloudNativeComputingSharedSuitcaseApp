"""SNS adapter that publishes the card result email notification.

The worker is the producer of the notification: it publishes one message
per verified card to the SNS topic owned by the 4_sns stack. The topic
subscription uses the email protocol, so the platform performs the actual
email delivery to the address read from the EMAIL_TO_NOTIFY key of the
secrets-pipeline-native-map secret; the worker never handles SMTP or
provider credentials, and no address is hardcoded here.

Error semantics: a publish failure raises, so the SQS invocation fails
and the queue redelivers the event; the notification is retried on the
next invocation, and the idempotent status update makes the retry safe.
The POR_VERIFICAR fallback publish is the only call that must not raise
(the invocation fails anyway), and the caller handles it.
"""

import json
import logging

import boto3

from config import Settings
from domain.ports.card_result_publisher_port import CardResultPublisherPort

logger = logging.getLogger(Settings.app_name)

# A boto3 SNS client (the boto3.client factory returns it lazily, so the
# annotation stays as a plain comment rather than a runtime type).
_client = None


def build_client(region_name: str | None = None):
    """Create an SNS boto3 client for the configured region."""
    return boto3.client("sns", region_name=region_name or Settings.aws_region)


def get_client():
    """Return the process-wide SNS client (singleton)."""
    global _client
    if _client is None:
        _client = build_client()
    return _client


def reset_client_for_tests() -> None:
    """Drop the singleton client (unit tests only)."""
    global _client
    _client = None


class SnsCardResultPublisherAdapter(CardResultPublisherPort):
    """Publishes the card result notification to the configured topic."""

    def __init__(self, topic_arn: str | None = None):
        self.topic_arn = (
            topic_arn if topic_arn is not None else Settings.card_result_topic_arn
        )

    def publish_card_result(
        self,
        card_id: str,
        status: str,
        ruv: str,
        last_four_digits: str,
        issuer: str,
        updated_at: str,
        owner_email: str,
    ) -> None:
        """Publish the email notification for the verified card."""
        if not self.topic_arn:
            logger.warning(
                "Card result topic not configured; skipping the email "
                "notification of card %s",
                card_id,
            )
            return

        get_client().publish(
            TopicArn=self.topic_arn,
            Subject=f"Card verification result: {status}",
            Message=json.dumps(
                {
                    "eventType": "CARD_RESULT",
                    "cardId": card_id,
                    "status": status,
                    "ruv": ruv,
                    "lastFourDigits": last_four_digits,
                    "issuer": issuer,
                    "updatedAt": updated_at,
                    "recipient": owner_email,
                },
                sort_keys=True,
            ),
        )
        logger.info(
            "Published the card result notification for card %s (status %s, "
            "recipient %s)",
            card_id,
            status,
            owner_email or "unresolved",
        )
