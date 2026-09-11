"""OfferInfo domain model for RF-005 aggregation.

An offer carries its score (nullable) after the Score service lookup.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OfferInfo:
    """Offer with resolved score for the 200 response body."""

    id: str
    userId: str
    description: str
    size: str  # LARGE | MEDIUM | SMALL
    fragile: bool
    offer: float  # value in USD
    score: float | None
    createdAt: str  # ISO-8601 datetime string
