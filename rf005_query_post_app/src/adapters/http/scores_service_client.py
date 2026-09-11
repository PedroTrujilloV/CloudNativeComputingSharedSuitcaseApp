"""HTTP client adapter for the Score service."""

import logging

import httpx

from config import Settings
from domain.ports.scores_port import ScoresPort


logger = logging.getLogger("rf005_query_post_app")


class ScoresServiceClient(ScoresPort):
    """Talks to the Score service's public API only.

    Contract reused as-is from ``scores_app`` (Entrega 2):
      - GET /scores?offerId={offer_id} -> 200 with score dict or {offerId, score: null}

    Resilience requirement (RF-005): the Score service "puede no ser
    consistente en el tiempo", so every failure mode of an individual
    lookup (network error, timeout, 5xx, malformed payload) degrades to
    ``None`` for that offer. The unavailability is logged for debugging
    during grading; the request itself must still succeed.
    """

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.scores_service_url,
            timeout=Settings.http_timeout,
        )

    def get_score(self, offer_id: str) -> float | None:
        """Fetch the score for an offer via the Score service.

        Returns:
            - float: the score value when a score exists.
            - None: when no score exists (404 or {"score": null}) or when
              the Score service is temporarily unavailable (network error,
              timeout, 5xx, or a malformed payload).

        This method never raises: per the RF-005 resilience requirement,
        every failure is isolated to the individual offer, which is
        returned with ``score: null`` while the rest of the response is
        unaffected. Unavailability events are logged so they can be
        tracked during grading.
        """
        try:
            response = self._client.get("/scores", params={"offerId": offer_id})
        except httpx.HTTPError as exc:
            logger.warning(
                "Score service unavailable for offer %s: %s. "
                "Returning score null for this offer.",
                offer_id,
                exc,
            )
            return None

        if response.status_code in (404, 200):
            try:
                data = response.json()
            except ValueError:
                logger.warning(
                    "Score service returned a non-JSON body (status %s) "
                    "for offer %s. Returning score null for this offer.",
                    response.status_code,
                    offer_id,
                )
                return None
            score_value = data.get("score")
            if score_value is None:
                return None
            try:
                return float(score_value)
            except (TypeError, ValueError):
                logger.warning(
                    "Score service returned a non-numeric score %r for "
                    "offer %s. Returning score null for this offer.",
                    score_value,
                    offer_id,
                )
                return None

        logger.warning(
            "Score service answered with status %s for offer %s. "
            "Returning score null for this offer.",
            response.status_code,
            offer_id,
        )
        return None

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
