"""HTTP client adapter for the Scores service."""

import httpx

from config import Settings
from domain.ports.scores_port import ScoresPort
from errors import ScoresServiceUnavailableError


class ScoresServiceClient(ScoresPort):
    """Talks to the Scores service's public API only."""

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.scores_service_url,
            timeout=Settings.http_timeout,
        )

    def upsert_score(self, offer_id: str, score_value: float) -> dict:
        """Persist or update a score via POST /scores."""
        payload = {
            "offerId": offer_id,
            "score": score_value,
        }
        try:
            response = self._client.post("/scores", json=payload)
        except httpx.HTTPError as exc:
            raise ScoresServiceUnavailableError(
                "The Scores service is temporarily unavailable"
            ) from exc

        if response.status_code not in (200, 201):
            # Per RF-004 resilience requirement: soft-fail.
            # The offer already exists, so this is not a hard failure.
            raise ScoresServiceUnavailableError(
                "The Scores service is temporarily unavailable"
            )

        return response.json()

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
