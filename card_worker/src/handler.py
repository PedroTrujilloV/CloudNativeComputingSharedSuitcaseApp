"""Lambda entry point of the card verification worker.

The function is triggered by the SQS event source mapping of the card
verification queue. Every record carries the verification event published
by the credit cards application; the use case polls TrueNative a bounded
number of times, updates the terminal status on the card, and publishes
the mandatory email notification of the result.

Error semantics: any raised error makes the invocation fail, so the queue
redelivers the event. After the maximum number of receives the event is
moved to the dead letter queue and the card stays POR_VERIFICAR, with the
fallback email published on the last receive (documented fallback of the
RF-006 pattern).
"""

import json
import logging

from assembly import build_verify_card_status_use_case
from config import Settings
from domain.models.card_verification_event import CardVerificationEvent
from errors import CardVerificationEventError

logger = logging.getLogger(Settings.app_name)


def parse_event(body: str) -> CardVerificationEvent:
    """Parse and validate the SQS record body as a verification event."""
    try:
        payload = json.loads(body)
    except ValueError:
        raise CardVerificationEventError("The record body is not valid JSON") from None
    if not isinstance(payload, dict):
        raise CardVerificationEventError("The record body is not a JSON object")
    try:
        return CardVerificationEvent(**payload)
    except ValueError as exc:
        raise CardVerificationEventError(str(exc)) from None


def receive_count_of(record: dict) -> int:
    """Read the receive count of an SQS record (1 for the first delivery)."""
    attributes = record.get("attributes", {}) if isinstance(record, dict) else {}
    raw = attributes.get("ApproximateReceiveCount", "1")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 1
    return value if value > 0 else 1


def handler(event: dict, context) -> None:  # noqa: ARG001
    """Process every record of the SQS batch (one card per invocation).

    The context argument is part of the Lambda handler contract; the
    worker does not use it (the invocation metadata is not needed by the
    flow).
    """
    use_case = build_verify_card_status_use_case()
    records = event.get("Records", []) if isinstance(event, dict) else []
    for record in records:
        body = record.get("body", "") if isinstance(record, dict) else ""
        card_event = parse_event(body)
        receive_count = receive_count_of(record)
        use_case.execute(card_event, receive_count)
        logger.info("Processed the verification event of card %s", card_event.cardId)
