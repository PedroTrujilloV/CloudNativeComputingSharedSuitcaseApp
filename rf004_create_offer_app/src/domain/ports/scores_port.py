"""Port for the Scores service (score persistence)."""

from abc import ABC, abstractmethod


class ScoresPort(ABC):
    """Abstraction over the Scores service's public API."""

    @abstractmethod
    def upsert_score(self, offer_id: str, score_value: float) -> dict:
        """Persist or update a score for an offer via POST /scores.

        Raises:
            ScoresServiceUnavailableError: the service is unreachable or
                fails (network error / 5xx).
        """


class FakeScores:
    """In-memory fake for the Scores service used in tests."""

    def __init__(self, upsert_result: dict | None = None):
        self.upsert_result = upsert_result or {
            "offerId": "offer-1",
            "score": 25000.0,
        }
        self.upsert_calls: list[dict] = []

    def upsert_score(self, offer_id: str, score_value: float) -> dict:
        self.upsert_calls.append({
            "offerId": offer_id,
            "score": score_value,
        })
        return self.upsert_result
