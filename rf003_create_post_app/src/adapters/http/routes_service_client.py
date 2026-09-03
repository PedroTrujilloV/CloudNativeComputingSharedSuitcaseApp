"""HTTP client adapter for the Routes service."""

from datetime import datetime

import httpx

from config import Settings
from domain.models.route import RouteInfo
from domain.ports.routes_port import RoutesPort
from errors import (
    RouteDatesInvalidError,
    RoutesServiceUnavailableError,
)


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (possibly with a ``Z`` suffix)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class RoutesServiceClient(RoutesPort):
    """Talks to the Routes service's public API only.

    Contract reused as-is from ``routes_app`` (Entrega 1):
      - ``GET /routes?flight={flightId}`` -> 200 with a list (possibly empty)
      - ``POST /routes`` -> 201 ``{id, createdAt}``, 412 when the flightId
        already exists or the journey dates are invalid, 400 on malformed
        input (e.g. airport codes that are not 3 uppercase letters).
    """

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.routes_service_url,
            timeout=Settings.http_timeout,
        )

    def find_by_flight_id(self, flight_id: str) -> RouteInfo | None:
        """Resolve the existing route for ``flight_id`` (or ``None``)."""
        try:
            response = self._client.get("/routes", params={"flight": flight_id})
        except httpx.HTTPError as exc:
            raise RoutesServiceUnavailableError(
                "The Routes service is temporarily unavailable"
            ) from exc

        if response.status_code != 200:
            raise RoutesServiceUnavailableError(
                "The Routes service is temporarily unavailable"
            )

        routes = response.json()
        if not routes:
            return None

        return self._to_route_info(routes[0])

    def create_route(
        self,
        flight_id: str,
        source_airport_code: str,
        source_country: str,
        destiny_airport_code: str,
        destiny_country: str,
        bag_cost: int,
        planned_start_date: datetime,
        planned_end_date: datetime,
    ) -> RouteInfo:
        """Create a route and return its minimal view."""
        body = {
            "flightId": flight_id,
            "sourceAirportCode": source_airport_code.upper(),
            "sourceCountry": source_country,
            "destinyAirportCode": destiny_airport_code.upper(),
            "destinyCountry": destiny_country,
            "bagCost": bag_cost,
            "plannedStartDate": planned_start_date.isoformat(),
            "plannedEndDate": planned_end_date.isoformat(),
        }

        try:
            response = self._client.post("/routes", json=body)
        except httpx.HTTPError as exc:
            raise RoutesServiceUnavailableError(
                "The Routes service is temporarily unavailable"
            ) from exc

        if response.status_code == 412:
            # Duplicate flightId or invalid journey dates: the Routes
            # service owns this rule, the orchestrator surfaces it as-is.
            raise RouteDatesInvalidError("Las fechas del trayecto no son válidas")
        if response.status_code != 201:
            raise RoutesServiceUnavailableError(
                "The Routes service is temporarily unavailable"
            )

        payload = response.json()
        created_at = payload.get("createdAt")
        return RouteInfo(
            id=str(payload["id"]),
            flightId=flight_id,
            plannedStartDate=planned_start_date,
            createdAt=_parse_datetime(created_at) if created_at else None,
        )

    def delete_route(self, route_id: str) -> None:
        """Delete a route (compensating action for the RF-003 saga).

        The Routes service (Entrega 1) exposes ``DELETE /routes/{id}``:
        ``200`` when the route was deleted, ``404`` when it does not exist.
        A ``404`` is treated as success for compensation purposes (there is
        nothing left to clean up); any network error or other status is a
        ``RoutesServiceUnavailableError`` so the caller can log the failed
        compensation.
        """
        try:
            response = self._client.delete(f"/routes/{route_id}")
        except httpx.HTTPError as exc:
            raise RoutesServiceUnavailableError(
                "The Routes service is temporarily unavailable"
            ) from exc

        if response.status_code not in (200, 404):
            raise RoutesServiceUnavailableError(
                "The Routes service is temporarily unavailable"
            )

    @staticmethod
    def _to_route_info(route: dict) -> RouteInfo:
        """Map a Routes-service route dict onto the orchestrator's view."""
        return RouteInfo(
            id=str(route["id"]),
            flightId=route["flightId"],
            plannedStartDate=_parse_datetime(route["plannedStartDate"]),
            createdAt=(
                _parse_datetime(route["createdAt"]) if route.get("createdAt") else None
            ),
        )

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
