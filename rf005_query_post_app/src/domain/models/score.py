"""ScoreInfo domain model for RF-005 aggregation.

A score row persisted by the Score (Utilidad) service.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreInfo:
    """Score (Utilidad) value resolved through the Score service API."""

    id: str
    offerId: str
    score: float
    createdAt: str  # ISO-8601 datetime string
