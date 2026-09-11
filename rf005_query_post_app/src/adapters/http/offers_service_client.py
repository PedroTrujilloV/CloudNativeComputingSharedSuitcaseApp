"""HTTP client adapter for the Offers service."""

import httpx

from config import Settings
from domain.ports.offers_port import OffersPort
from errors import OffersServiceUnavailableError


class OffersServiceClient(OffersPort):
    """Talks to the Offers service's public API only.

    Contract reused as-is from ``offers_app`` (Entrega 1):
      - GET /offers?post={post_id} -> 200 with a list of offer dicts
        (empty list when no offers exist)
    """

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.offers_service_url,
            timeout=Settings.http_timeout,
        )

    def get_offers(self, post_id: str) -> list[dict]:
        """Fetch all offers for a given post id via the Offers service."""
        try:
            response = self._client.get("/offers", params={"post": post_id})
        except httpx.HTTPError as exc:
            raise OffersServiceUnavailableError(
                "The Offers service is temporarily unavailable"
            ) from exc

        if response.status_code == 400:
            # Invalid UUID format passed to the Offers service.
            # Treat as empty list since no valid offers can match.
            return []
        if response.status_code != 200:
            raise OffersServiceUnavailableError(
                "The Offers service is temporarily unavailable"
            )

        return response.json()

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
