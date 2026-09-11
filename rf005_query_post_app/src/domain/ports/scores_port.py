"""Scores port (contract) for the RF-005 orchestrator."""

from abc import ABC, abstractmethod


class ScoresPort(ABC):
    """Abstraction over the Score service public API."""

    @abstractmethod
    def get_score(self, offer_id: str) -> float | None:
        """Fetch the score for an offer via the Score service.

        Returns None when no score exists or when the Score service is
        temporarily unavailable (resilient per-offer fallback). This
        method must never raise: the RF-005 resilience requirement
        isolates every score failure to the individual offer, which is
        then returned with ``score: null`` while the rest of the
        response is unaffected.
        """
