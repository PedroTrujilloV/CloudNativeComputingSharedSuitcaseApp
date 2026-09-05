"""HTTP client adapter for the Routes service."""

import httpx

from config import Settings
from domain.models.route import RouteInfo
from domain.ports.routes_port import RoutesPort
from errors import RouteNotFoundError, RoutesServiceUnavailableError


class RoutesServiceClient(RoutesPort):
    """Talks to the Routes service's public API only."""

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.routes_service_url,
            timeout=Settings.http_timeout,
        )

    def get_route(self, route_id: str) -> RouteInfo:
        """Fetch a route by id and return its minimal view."""
        try:
            response = self._client.get(f"/routes/{route_id}")
        except httpx.HTTPError as exc:
            raise RoutesServiceUnavailableError(
                "The Routes service is temporarily unavailable"
            ) from exc

        if response.status_code == 404:
            raise RouteNotFoundError(f"Route {route_id} does not exist")
        if response.status_code != 200:
            raise RoutesServiceUnavailableError(
                "The Routes service is temporarily unavailable"
            )

        payload = response.json()
        return RouteInfo(
            id=str(payload["id"]),
            bagCost=float(payload["bagCost"]),
        )

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
