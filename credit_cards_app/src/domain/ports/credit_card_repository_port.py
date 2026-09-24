from abc import ABC, abstractmethod

from domain.models.credit_card import CardStatus, CreditCard


class CreditCardRepositoryPort(ABC):
    """Persistence contract for the CreditCard entity.

    The application is the exclusive owner of this data: only this component
    (and the card worker through the same DynamoDB API) talks to the table.
    """

    @abstractmethod
    def create(self, card: CreditCard) -> CreditCard:
        """Persist a new card and return the stored entity."""

    @abstractmethod
    def get_by_id(self, card_id: str) -> CreditCard | None:
        """Return the card with the given id, or None when it does not exist."""

    @abstractmethod
    def search(self, user_id: str | None = None) -> list[CreditCard]:
        """Return the stored cards, optionally filtered by the owner."""

    @abstractmethod
    def update_status(
        self, card_id: str, status: CardStatus
    ) -> CreditCard | None:
        """Change the card status and refresh updatedAt; None when missing."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of stored cards."""

    @abstractmethod
    def delete_all(self) -> int:
        """Delete every stored card and return the deleted count."""
