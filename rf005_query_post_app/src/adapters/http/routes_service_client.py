"""HTTP client adapter for the Routes service."""

import httpx

from config import Settings
from domain.models.route import Point, RouteInfo
from domain.ports.routes_port import RoutesPort
from errors import RouteNotFoundError, RoutesServiceUnavailableError


class RoutesServiceClient(RoutesPort):
    """Talks to the Routes service's public API only.

    Contract reused as-is from ``routes_app`` (Entrega 1):
      - ``GET /routes/{route_id}`` -> 200 with a route dict, 404 when not found.
    """

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.routes_service_url,
            timeout=Settings.http_timeout,
        )

    def get_route(self, route_id: str) -> RouteInfo:
        """Fetch a single route by id via the Routes service."""
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

        return self._to_route_info(response.json())

    @staticmethod
    def _to_route_info(route: dict) -> RouteInfo:
        """Map a Routes-service route dict onto the orchestrator's view."""
        origin = Point(
            airportCode=route.get("sourceAirportCode", ""),
            country=route.get("sourceCountry", ""),
        )
        destiny = Point(
            airportCode=route.get("destinyAirportCode", ""),
            country=route.get("destinyCountry", ""),
        )
        return RouteInfo(
            id=str(route["id"]),
            flightId=route.get("flightId", ""),
            origin=origin,
            destiny=destiny,
            bagCost=route.get("bagCost", 0),
            plannedStartDate=route.get("plannedStartDate", ""),
            plannedEndDate=route.get("plannedEndDate", ""),
        )

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
