"""Routes port (contract) for the RF-005 orchestrator."""

from abc import ABC, abstractmethod


class RoutesPort(ABC):
    """Abstraction over the Routes service public API."""

    @abstractmethod
    def get_route(self, route_id: str):
        """Fetch a single route by its id via the Routes service.

        Raises:
            RouteNotFoundError: when the route does not exist.
            RoutesServiceUnavailableError: when the service is unreachable
                or errors (network error / 5xx).
        """
