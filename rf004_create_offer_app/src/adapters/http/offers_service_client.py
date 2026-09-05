"""HTTP client adapter for the Offers service."""

import httpx

from config import Settings
from domain.ports.offers_port import OffersPort
from errors import OffersServiceUnavailableError


class OffersServiceClient(OffersPort):
    """Talks to the Offers service's public API only."""

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.offers_service_url,
            timeout=Settings.http_timeout,
        )

    def create_offer(
        self,
        postId: str,
        userId: str,
        description: str,
        size: str,
        fragile: bool,
        offer: float,
    ) -> dict:
        """Create an offer via POST /offers."""
        payload = {
            "postId": postId,
            "userId": userId,
            "description": description,
            "size": size,
            "fragile": fragile,
            "offer": offer,
        }
        try:
            response = self._client.post("/offers", json=payload)
        except httpx.HTTPError as exc:
            raise OffersServiceUnavailableError(
                "The Offers service is temporarily unavailable"
            ) from exc

        if response.status_code in (400, 412):
            # Business validation error - offer creation failed
            raise OffersServiceUnavailableError(
                "The Offers service returned an error"
            )
        if response.status_code != 201:
            raise OffersServiceUnavailableError(
                "The Offers service is temporarily unavailable"
            )

        return response.json()

    def delete_offer(self, offer_id: str) -> None:
        """Delete an offer via DELETE /offers/{id} (compensating action)."""
        try:
            response = self._client.delete(f"/offers/{offer_id}")
        except httpx.HTTPError as exc:
            raise OffersServiceUnavailableError(
                "The Offers service is temporarily unavailable"
            ) from exc

        if response.status_code not in (200, 204):
            raise OffersServiceUnavailableError(
                "The Offers service is temporarily unavailable"
            )

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
