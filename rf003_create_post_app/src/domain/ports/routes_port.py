"""Port for the Routes service (find-or-create a route by flightId)."""

from abc import ABC, abstractmethod
from datetime import datetime

from domain.models.route import RouteInfo


class RoutesPort(ABC):
    """Abstraction over the Routes service's public API."""

    @abstractmethod
    def find_by_flight_id(self, flight_id: str) -> RouteInfo | None:
        """Return the existing route for ``flight_id`` or ``None`` if absent."""

    @abstractmethod
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
        """Create a route via the Routes service and return its minimal view.

        Raises:
            RouteDatesInvalidError: if the Routes service answers 412.
            RoutesServiceUnavailableError: if the service is unreachable.
        """

    @abstractmethod
    def delete_route(self, route_id: str) -> None:
        """Delete a route via the Routes service (compensating action).

        Used by the RF-003 saga compensation: when the post creation fails
        after a *new* route was created, the orchestrator deletes that route
        so no orphaned route record survives the failed request.

        Raises:
            RoutesServiceUnavailableError: if the service is unreachable or
                answers an unexpected status (the compensation could not be
                confirmed; the caller must log and report the failure).
        """
