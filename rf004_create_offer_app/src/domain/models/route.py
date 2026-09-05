"""Route data model for the RF-004 orchestrator."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteInfo:
    """Minimal route view resolved through the Routes service API."""

    id: str
    bagCost: float
