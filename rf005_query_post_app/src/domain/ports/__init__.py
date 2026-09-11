"""Ports for the RF-005 orchestrator."""

from abc import ABC, abstractmethod

from domain.models import PostInfo


class PostsPort(ABC):
    """Abstraction over the Posts service's public API."""

    @abstractmethod
    def get_post(self, post_id: str) -> PostInfo:
        """Fetch a post by id via the Posts service.

        Raises:
            PostNotFoundError: the Posts service answers 404 (the post does
                not exist).
            PostsServiceUnavailableError: the service is unreachable or
                fails (network error / 5xx).
        """
