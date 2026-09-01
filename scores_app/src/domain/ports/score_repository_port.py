from abc import ABC, abstractmethod

from domain.models.score import Score


class ScoreRepositoryPort(ABC):
    """Persistence contract for the Score (Utilidad) entity.

    Team decision (schema design): one current score row per offer. Updates
    replace the value in place (no history table), so ``get_by_offer_id``
    always returns the latest persisted value for an offer.
    """

    @abstractmethod
    def upsert(self, score: Score) -> Score:
        """Create the score for an offer, or update its value in place."""

    @abstractmethod
    def get_by_id(self, score_id: str) -> Score | None:
        """Return the persisted score by its id, or ``None`` when absent."""

    @abstractmethod
    def get_by_offer_id(self, offer_id: str) -> Score | None:
        """Return the persisted score for an offer, or ``None`` when the
        offer has no score defined yet (null-safe, never raises)."""

    @abstractmethod
    def delete(self, offer_id: str) -> bool:
        """Delete the score for an offer. Returns ``False`` when absent."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of persisted scores."""

    @abstractmethod
    def delete_all(self) -> int:
        """Delete all persisted scores. Returns the number of rows removed."""
