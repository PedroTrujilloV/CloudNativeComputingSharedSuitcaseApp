"""Response DTOs for RF-005 endpoint.

These models shape the exact 200 response documented in the API contract.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteResponse:
    """Route part of the 200 response (nested inside data)."""

    id: str
    flightId: str
    origin: dict  # { "airportCode": "...", "country": "..." }
    destiny: dict  # { "airportCode": "...", "country": "..." }
    bagCost: int


@dataclass(frozen=True)
class OfferResponse:
    """Offer part of the 200 response array (each element)."""

    id: str
    userId: str
    description: str
    size: str  # LARGE | MEDIUM | SMALL
    fragile: bool
    offer: float
    score: float | None
    createdAt: str


@dataclass(frozen=True)
class QueryPostResponse:
    """Full 200 response body shaped as documented for RF-005."""

    data: dict  # { id, expireAt, route, plannedStartDate, plannedEndDate, createdAt, offers }
