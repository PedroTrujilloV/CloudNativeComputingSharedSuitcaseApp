"""Port for publishing the card verification event to the queue.

The asynchronous hand off of the RF-006 flow: once the card is persisted as
POR_VERIFICAR, the event travels through the SQS queue to the card worker,
which polls TrueNative and updates the terminal status. Publishing this
event is the only way the web component talks to the verification pipeline;
no in process async is used.
"""

from abc import ABC, abstractmethod


class CardEventPublisherPort(ABC):
    """Driven interface for the card verification queue hand off."""

    @abstractmethod
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
        """Send the verification event for a freshly stored card.

        The event carries the card id and the RUV (the worker polls TrueNative
        with the RUV and updates the card by id), plus the stored card data
        and the owner email (resolved through the users application API)
        so the eventual email notification is self contained.

        Implementations must not raise for a publish failure of the hand off
        itself: the card is already stored as POR_VERIFICAR, which is a
        valid state, and failing the user request after a successful
        tokenization would turn the retry into a duplicate conflict. The
        failure is logged instead.
        """
