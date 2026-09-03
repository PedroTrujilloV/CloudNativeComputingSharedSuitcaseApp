"""Route data model for the RF-003 orchestrator.

The orchestrator is stateless: it never owns route data, only the minimal
subset of it returned by the Routes service that the post-creation flow
needs (the route id, its creation timestamp and the planned start date).
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RouteInfo:
    """Minimal route view resolved through the Routes service API."""

    id: str
    flightId: str
    plannedStartDate: datetime
    createdAt: datetime | None = None
