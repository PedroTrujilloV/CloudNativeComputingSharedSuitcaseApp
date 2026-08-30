"""SQLAlchemy Route repository adapter."""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from adapters.database.models import SQLAlchemyRouteModel
from domain.models.route import Route
from domain.ports.route_repository_port import RouteRepositoryPort
from errors import RouteAlreadyExistsError
from domain.services.route_validation import validate_route_dates


class SQLAlchemyRouteRepositoryAdapter(RouteRepositoryPort):
    """SQLAlchemy implementation of RouteRepositoryPort."""

    def __init__(self, session: Session):
        """Initialize the repository with a database session.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session
        self._route_model = SQLAlchemyRouteModel

    def create(self, route: Route) -> Route:
        """Persist a new route.

        Args:
            route: Route domain model to persist.

        Returns:
            The persisted route with database-generated fields.

        Raises:
            ValueError: If route dates are invalid.
            RouteAlreadyExistsError: If flightId already exists.
        """
        # Validate dates before persistence
        validate_route_dates(route.plannedStartDate, route.plannedEndDate)

        # Generate UUID if not provided
        import uuid
        if not route.id:
            route.id = str(uuid.uuid4())

        # Check for duplicate flightId before persisting
        existing = self.session.query(self._route_model).filter(
            self._route_model.flightId == route.flightId
        ).first()
        if existing:
            raise RouteAlreadyExistsError(
                f"Route with flightId '{route.flightId}' already exists"
            )

        # Create ORM model from domain model
        orm_route = self._route_model(
            id=route.id,
            flightId=route.flightId,
            sourceAirportCode=route.sourceAirportCode,
            sourceCountry=route.sourceCountry,
            destinyAirportCode=route.destinyAirportCode,
            destinyCountry=route.destinyCountry,
            bagCost=route.bagCost,
            plannedStartDate=route.plannedStartDate,
            plannedEndDate=route.plannedEndDate,
            createdAt=route.createdAt or datetime.utcnow(),
            updatedAt=datetime.utcnow(),
        )

        self.session.add(orm_route)
        self.session.commit()
        self.session.refresh(orm_route)

        return orm_route.to_route()

    def get_by_id(self, route_id: str) -> Optional[Route]:
        """Get route by id.

        Args:
            route_id: The route UUID.

        Returns:
            Route if found, None otherwise.
        """
        orm_route = self.session.query(self._route_model).filter(
            self._route_model.id == route_id
        ).first()

        if not orm_route:
            return None
        return orm_route.to_route()

    def get_by_flight_id(self, flight_id: str) -> Optional[Route]:
        """Get route by flightId.

        Args:
            flight_id: The flight identifier (e.g., AA001).

        Returns:
            Route if found, None otherwise.
        """
        orm_route = self.session.query(self._route_model).filter(
            self._route_model.flightId == flight_id
        ).first()

        if not orm_route:
            return None
        return orm_route.to_route()

    def list_routes(self, flight_id: Optional[str] = None) -> list[Route]:
        """List routes, optionally filtered by flightId.

        Args:
            flight_id: Optional flightId to filter by.

        Returns:
            List of routes matching the filter (or all routes if no filter).
        """
        query = self.session.query(self._route_model)
        if flight_id:
            query = query.filter(self._route_model.flightId == flight_id)
        orm_routes = query.all()
        return [orm_route.to_route() for orm_route in orm_routes]

    def delete(self, route: Route) -> bool:
        """Delete a route by id.

        Args:
            route: The route to delete (must have id set).

        Returns:
            True if route was deleted, False otherwise.
        """
        if not route.id:
            raise ValueError("Cannot delete route without id")

        result = self.session.query(self._route_model).filter(
            self._route_model.id == route.id
        ).delete()

        self.session.commit()
        return result > 0

    def delete_by_id(self, route_id: str) -> bool:
        """Delete a route by its UUID.

        Args:
            route_id: The route UUID.

        Returns:
            True if route was deleted, False otherwise.
        """
        result = self.session.query(self._route_model).filter(
            self._route_model.id == route_id
        ).delete()

        self.session.commit()
        return result > 0

    def count(self) -> int:
        """Count persisted routes.

        Returns:
            Number of routes in the repository.
        """
        return self.session.query(self._route_model).count()

    def delete_all(self) -> None:
        """Delete all routes (reset)."""
        self.session.query(self._route_model).delete()
        self.session.commit()
