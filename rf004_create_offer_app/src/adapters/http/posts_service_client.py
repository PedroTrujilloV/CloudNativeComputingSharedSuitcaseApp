"""HTTP client adapter for the Posts service."""

from datetime import datetime

import httpx

from config import Settings
from domain.models.post import PostInfo
from domain.ports.posts_port import PostsPort
from errors import (
    PostNotFoundError,
    PostsServiceUnavailableError,
)


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (possibly with a ``Z`` suffix)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class PostsServiceClient(PostsPort):
    """Talks to the Posts service's public API only.

    Contract reused as-is from ``posts_app`` (Entrega 1):
      - ``GET /posts/{id}`` -> 200 ``{id, routeId, userId, expireAt,
        createdAt}``, 404 when the post does not exist, 400 when the id is
        not a valid UUID.
    """

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.posts_service_url,
            timeout=Settings.http_timeout,
        )

    def get_post(self, post_id: str) -> PostInfo:
        """Fetch a post by id and return its minimal view."""
        try:
            response = self._client.get(f"/posts/{post_id}")
        except httpx.HTTPError as exc:
            raise PostsServiceUnavailableError(
                "The Posts service is temporarily unavailable"
            ) from exc

        if response.status_code == 404:
            # Unknown post id (including non-UUID ids, which the Posts
            # service rejects with 400): for the caller the post simply
            # does not exist.
            raise PostNotFoundError(f"Post {post_id} does not exist")
        if response.status_code == 400:
            raise PostNotFoundError(f"Post {post_id} does not exist")
        if response.status_code != 200:
            raise PostsServiceUnavailableError(
                "The Posts service is temporarily unavailable"
            )

        payload = response.json()
        return PostInfo(
            id=str(payload["id"]),
            routeId=str(payload["routeId"]),
            userId=str(payload["userId"]),
            expireAt=_parse_datetime(payload["expireAt"]),
        )

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
