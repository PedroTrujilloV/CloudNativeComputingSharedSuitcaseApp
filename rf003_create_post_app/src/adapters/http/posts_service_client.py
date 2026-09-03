"""HTTP client adapter for the Posts service."""

from datetime import datetime

import httpx

from config import Settings
from domain.ports.posts_port import CreatedPost, PostsPort
from errors import (
    ExpireAtInvalidError,
    PostsServiceUnavailableError,
)


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (possibly with a ``Z`` suffix)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class PostsServiceClient(PostsPort):
    """Talks to the Posts service's public API only.

    Contract reused as-is from ``posts_app`` (Entrega 1):
      - ``GET /posts?route={routeId}&owner={userId}`` -> 200 with a list
        (possibly empty) of the owner's posts for the route
      - ``POST /posts`` -> 201 ``{id, userId, createdAt}``, 412 when
        ``expireAt`` is not in the future, 400 on malformed input.
    """

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.posts_service_url,
            timeout=Settings.http_timeout,
        )

    def has_post_for_route_and_owner(self, route_id: str, owner_id: str) -> bool:
        """Return True when the owner already has a post for the route."""
        try:
            response = self._client.get(
                "/posts", params={"route": route_id, "owner": owner_id}
            )
        except httpx.HTTPError as exc:
            raise PostsServiceUnavailableError(
                "The Posts service is temporarily unavailable"
            ) from exc

        if response.status_code != 200:
            raise PostsServiceUnavailableError(
                "The Posts service is temporarily unavailable"
            )

        return bool(response.json())

    def create_post(
        self, route_id: str, user_id: str, expire_at: datetime
    ) -> CreatedPost:
        """Create a post and return its minimal view."""
        body = {
            "routeId": route_id,
            "userId": user_id,
            "expireAt": expire_at.isoformat(),
        }

        try:
            response = self._client.post("/posts", json=body)
        except httpx.HTTPError as exc:
            raise PostsServiceUnavailableError(
                "The Posts service is temporarily unavailable"
            ) from exc

        if response.status_code == 412:
            # The Posts service owns the "expireAt must be in the future"
            # rule; the orchestrator surfaces it with the documented message.
            raise ExpireAtInvalidError("La fecha expiración no es válida")
        if response.status_code != 201:
            raise PostsServiceUnavailableError(
                "The Posts service is temporarily unavailable"
            )

        payload = response.json()
        return CreatedPost(
            id=str(payload["id"]),
            userId=str(payload["userId"]),
            createdAt=_parse_datetime(payload["createdAt"]),
        )

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
