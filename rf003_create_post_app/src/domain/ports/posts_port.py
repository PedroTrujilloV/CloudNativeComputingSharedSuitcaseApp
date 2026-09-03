"""Port for the Posts service (post creation + duplicate lookup)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CreatedPost:
    """Minimal view of a post as returned by the Posts service (201)."""

    id: str
    userId: str
    createdAt: datetime


class PostsPort(ABC):
    """Abstraction over the Posts service's public API."""

    @abstractmethod
    def has_post_for_route_and_owner(self, route_id: str, owner_id: str) -> bool:
        """Return True when the owner already has a post for the route."""

    @abstractmethod
    def create_post(
        self, route_id: str, user_id: str, expire_at: datetime
    ) -> CreatedPost:
        """Create a post via the Posts service and return its minimal view.

        Raises:
            ExpireAtInvalidError: if the Posts service answers 412.
            PostsServiceUnavailableError: if the service is unreachable.
        """
