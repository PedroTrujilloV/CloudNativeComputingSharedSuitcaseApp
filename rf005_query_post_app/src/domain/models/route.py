"""RouteInfo domain model for RF-005 aggregation.

This is the minimal route view returned by the Routes service and shaped
into the nested ``route`` object in the 200 response.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    """Airport information (origin or destiny)."""

    airportCode: str
    country: str


@dataclass(frozen=True)
class RouteInfo:
    """Minimal route view resolved through the Routes service API."""

    id: str
    flightId: str
    origin: Point
    destiny: Point
    bagCost: int
    plannedStartDate: str  # ISO-8601 datetime string
    plannedEndDate: str  # ISO-8601 datetime string
