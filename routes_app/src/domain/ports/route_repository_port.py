"""Route repository port (interface)."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


from domain.models.route import Route


class RouteRepositoryPort(ABC):
    """Route repository interface."""

    @abstractmethod
    def create(self, route: Route) -> Route:
        """Persist a new route."""
        pass

    @abstractmethod
    def get_by_id(self, route_id: str) -> Optional[Route]:
        """Get route by id."""
        pass

    @abstractmethod
    def get_by_flight_id(self, flight_id: str) -> Optional[Route]:
        """Get route by flightId."""
        pass

    @abstractmethod
    def list_routes(self, flight_id: Optional[str] = None) -> list[Route]:
        """List routes, optionally filtered by flightId.

        Args:
            flight_id: Optional flightId to filter by.

        Returns:
            List of routes matching the filter (or all routes if no filter).
        """
        pass

    @abstractmethod
    def delete(self, route: Route) -> bool:
        """Delete a route by id."""
        pass

    @abstractmethod
    def delete_by_id(self, route_id: str) -> bool:
        """Delete a route by its UUID.

        Args:
            route_id: The route UUID.

        Returns:
            True if route was deleted, False otherwise.
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """Count persisted routes."""
        pass

    @abstractmethod
    def delete_all(self) -> None:
        """Delete all routes (reset)."""
        pass
