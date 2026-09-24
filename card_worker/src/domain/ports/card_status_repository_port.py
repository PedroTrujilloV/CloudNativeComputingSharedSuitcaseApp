from abc import ABC, abstractmethod

from domain.models.card_status import CardStatus


class CardStatusRepositoryPort(ABC):
    """Port that persists the terminal status of a card."""

    @abstractmethod
    def update_status(self, card_id: str, status: CardStatus) -> None:
        """Set the terminal status of the card and refresh its updatedAt.

        The update is by card id, so it is idempotent under the at least
        once delivery of the queue: a card that already carries the same
        terminal status is left untouched.
        """
