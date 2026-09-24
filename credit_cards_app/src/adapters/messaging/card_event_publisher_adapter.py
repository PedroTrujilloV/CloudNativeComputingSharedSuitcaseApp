"""SQS adapter that publishes the card verification events.

The queue is the single asynchronous seam of the RF-006 flow: the event
travels from this application to the card worker, which polls TrueNative
and updates the terminal card status. The publisher follows the port
contract: a missing queue configuration is logged and skipped (the
application can run before the serverless stack of the worker lands), and
a publish failure is logged instead of raised, because the card is already
stored as POR_VERIFICAR, which is a valid state.
"""

import json
import logging

import boto3

from config import Settings
from domain.ports.card_event_publisher_port import CardEventPublisherPort

logger = logging.getLogger(Settings.app_name)

# A boto3 SQS client (the boto3.client factory returns it lazily, so the
# annotation stays as a plain comment rather than a runtime type).
_client = None


def build_client(region_name: str | None = None):
    """Create an SQS boto3 client for the configured region."""
    return boto3.client("sqs", region_name=region_name or Settings.aws_region)


def get_client():
    """Return the process-wide SQS client (singleton)."""
    global _client
    if _client is None:
        _client = build_client()
    return _client


def reset_client_for_tests() -> None:
    """Drop the singleton client (unit tests only)."""
    global _client
    _client = None


class SqsCardEventPublisherAdapter(CardEventPublisherPort):
    """Publishes the verification events to the configured SQS queue."""

    def __init__(self, queue_url: str | None = None):
        self.queue_url = queue_url if queue_url is not None else (
            Settings.card_verification_queue_url
        )

    def publish_verification_event(
        self,
        card_id: str,
        ruv: str,
        user_id: str,
        owner_email: str,
        last_four_digits: str,
        issuer: str,
        status: str,
        created_at: str,
    ) -> None:
        """Send the verification event for a freshly stored card."""
        if not self.queue_url:
            logger.warning(
                "Card verification queue not configured; skipping the "
                "verification event for card %s",
                card_id,
            )
            return

        event = {
            "eventType": "CARD_VERIFICATION_REQUESTED",
            "cardId": card_id,
            "ruv": ruv,
            "userId": user_id,
            "ownerEmail": owner_email,
            "lastFourDigits": last_four_digits,
            "issuer": issuer,
            "status": status,
            "createdAt": created_at,
        }
        try:
            get_client().send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(event),
            )
        except Exception:
            # The card is stored as POR_VERIFICAR, which is a valid state;
            # failing the user request after a successful tokenization would
            # turn the retry into a duplicate conflict. The failure is left
            # to the operators through the log.
            logger.exception(
                "Failed to publish the verification event for card %s; the "
                "card stays POR_VERIFICAR",
                card_id,
            )
