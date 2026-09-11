"""Post data model for the RF-005 orchestrator.

The orchestrator is stateless: it never owns post data, only the minimal
subset of it returned by the Posts service that the ownership gate and
aggregation need.
"""

from dataclasses import dataclass

from domain.models.offer import OfferInfo
from domain.models.response import OfferResponse, QueryPostResponse, RouteResponse
from domain.models.route import Point, RouteInfo
from domain.models.score import ScoreInfo

__all__ = [
    "OfferInfo",
    "OfferResponse",
    "Point",
    "PostInfo",
    "PostMinimalInfo",
    "QueryPostResponse",
    "RouteInfo",
    "RouteResponse",
    "ScoreInfo",
]


@dataclass(frozen=True)
class PostInfo:
    """Post view resolved through the Posts service API."""

    id: str
    userId: str
    routeId: str | None = None
    expireAt: str | None = None
    plannedStartDate: str | None = None
    plannedEndDate: str | None = None
    createdAt: str | None = None


@dataclass(frozen=True)
class PostMinimalInfo:
    """Minimal post view used by the ownership gate only."""

    id: str
    userId: str
