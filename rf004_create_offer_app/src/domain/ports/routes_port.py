"""Port for the Routes service (route lookup for score calculation)."""

from abc import ABC, abstractmethod

from domain.models.route import RouteInfo


class RoutesPort(ABC):
    """Abstraction over the Routes service's public API."""

    @abstractmethod
    def get_route(self, route_id: str) -> RouteInfo:
        """Fetch a route by id via the Routes service.

        Raises:
            RouteNotFoundError: the route does not exist (HTTP 404).
            RoutesServiceUnavailableError: the service is unreachable or
                fails (network error / 5xx).
        """
