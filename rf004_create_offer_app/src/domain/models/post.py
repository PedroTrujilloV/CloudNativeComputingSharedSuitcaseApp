"""Post data model for the RF-004 orchestrator.

The orchestrator is stateless: it never owns post data, only the minimal
subset of it returned by the Posts service that the offer preconditions
need (the post id, its route, its owner and its expiration date).
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PostInfo:
    """Minimal post view resolved through the Posts service API."""

    id: str
    routeId: str
    userId: str
    expireAt: datetime
