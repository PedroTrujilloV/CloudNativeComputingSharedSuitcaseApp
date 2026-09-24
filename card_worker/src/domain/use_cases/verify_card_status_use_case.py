"""Bounded polling use case of the card verification worker.

The function is synchronous code invoked by the queue: it polls TrueNative
a bounded number of times inside a single invocation. When a terminal
state is reached, it updates the card by id (idempotent under the at least
once delivery of the queue) and publishes the mandatory email
notification of the result. When the attempts are exhausted, it raises,
so the queue redelivers the event and the card stays POR_VERIFICAR until
the next invocation; on the last receive (the one after which the event
moves to the dead letter queue) it publishes the POR_VERIFICAR fallback
notification first, so the owner is never left without the mandatory
email.
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

from config import Settings
from domain.models.card_status import CardStatus
from domain.models.card_verification_event import CardVerificationEvent
from domain.ports.card_result_publisher_port import CardResultPublisherPort
from domain.ports.card_status_repository_port import CardStatusRepositoryPort
from domain.ports.true_native_poller_port import TrueNativeCardPollerPort
from errors import CardVerificationPendingError

logger = logging.getLogger(Settings.app_name)

# Date contract of the entity (same as the credit cards application).
ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%S"


def format_iso_utc(value: datetime) -> str:
    """Render a datetime in the entity contract format (UTC, seconds)."""
    return value.astimezone(timezone.utc).strftime(ISO_UTC_FORMAT)


class VerifyCardStatusUseCase:
    """Poll TrueNative until a terminal state, persist it, and notify."""

    def __init__(
        self,
        poller: TrueNativeCardPollerPort,
        repository: CardStatusRepositoryPort,
        publisher: CardResultPublisherPort,
        max_attempts: int | None = None,
        interval_seconds: float | None = None,
        max_receives: int | None = None,
        sleep: Callable[[float], None] | None = None,
    ):
        self.poller = poller
        self.repository = repository
        self.publisher = publisher
        self.max_attempts = (
            max_attempts
            if max_attempts is not None
            else Settings.poll_max_attempts
        )
        self.interval_seconds = (
            interval_seconds
            if interval_seconds is not None
            else Settings.poll_interval_seconds
        )
        self.max_receives = (
            max_receives if max_receives is not None else Settings.max_receive_count
        )
        # Injectable for the unit tests; the production path uses time.sleep.
        self.sleep = sleep if sleep is not None else time.sleep

    def execute(
        self, event: CardVerificationEvent, receive_count: int = 1
    ) -> CardStatus:
        """Run the bounded polling loop, persist the terminal state, notify.

        The publish of the terminal state raises on failure so the queue
        redelivers the event and the notification is retried (the status
        update is idempotent by card id, so the retry is safe).
        """
        card_id = event.cardId
        for attempt in range(1, self.max_attempts + 1):
            if attempt > 1:
                self.sleep(self.interval_seconds)
            result = self.poller.check_status(event.ruv)
            if result.terminal:
                status = CardStatus(result.status)
                self.repository.update_status(card_id, status)
                self.publisher.publish_card_result(
                    card_id=card_id,
                    status=status.value,
                    ruv=event.ruv,
                    last_four_digits=event.lastFourDigits,
                    issuer=event.issuer,
                    updated_at=format_iso_utc(datetime.now(timezone.utc)),
                    owner_email=event.ownerEmail,
                )
                logger.info(
                    "Card %s reached the terminal state %s (attempt %d); "
                    "the email notification was published",
                    card_id,
                    status.value,
                    attempt,
                )
                return status
        if receive_count >= self.max_receives:
            self._publish_fallback_notification(event)
        logger.warning(
            "Card %s still without a terminal state after %d attempts; "
            "the event will be redelivered by the queue",
            card_id,
            self.max_attempts,
        )
        raise CardVerificationPendingError(
            f"No terminal state for card {card_id} within the bounded attempts"
        )

    def _publish_fallback_notification(self, event: CardVerificationEvent) -> None:
        """Publish the POR_VERIFICAR email before the event hits the DLQ.

        The invocation fails anyway (the pending error is raised by the
        caller), so a publish failure is logged instead of raised: the
        event moves to the dead letter queue either way.
        """
        try:
            self.publisher.publish_card_result(
                card_id=event.cardId,
                status=CardStatus.POR_VERIFICAR.value,
                ruv=event.ruv,
                last_four_digits=event.lastFourDigits,
                issuer=event.issuer,
                updated_at=format_iso_utc(datetime.now(timezone.utc)),
                owner_email=event.ownerEmail,
            )
        except Exception:
            logger.exception(
                "Failed to publish the POR_VERIFICAR fallback notification "
                "of card %s; the event moves to the dead letter queue",
                event.cardId,
            )
