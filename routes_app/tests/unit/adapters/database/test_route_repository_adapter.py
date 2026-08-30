"""Unit tests for SQLAlchemy Route repository adapter."""
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.database.models import Base, RouteModel
from adapters.database.connection import get_engine, reset_engine_for_tests
from adapters.database.route_repository_adapter import SQLAlchemyRouteRepositoryAdapter
from domain.models.route import Route
from errors import RouteAlreadyExistsError


class TestSQLAlchemyRouteRepositoryAdapter:
    """Tests for SQLAlchemyRouteRepositoryAdapter."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test database."""
        reset_engine_for_tests()
        yield
        reset_engine_for_tests()

    @pytest.fixture
    def session(self):
        """Create test database session."""
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        session = SessionLocal()
        yield session
        session.close()

    @pytest.fixture
    def repository(self, session):
        """Create repository instance."""
        return SQLAlchemyRouteRepositoryAdapter(session)

    @pytest.fixture
    def valid_route(self):
        """Create a valid route."""
        future_start = datetime.utcnow() + timedelta(days=1)
        future_end = future_start + timedelta(days=1)

        return Route(
            flightId="AA123",
            sourceAirportCode="JFK",
            sourceCountry="United States",
            destinyAirportCode="MIA",
            destinyCountry="United States",
            bagCost=50,
            plannedStartDate=future_start,
            plannedEndDate=future_end,
        )

    def test_create_route_success(self, repository, valid_route, session):
        """Test creating a route successfully."""
        created_route = repository.create(valid_route)

        assert created_route.flightId == "AA123"
        assert created_route.bagCost == 50
        assert created_route.sourceAirportCode == "JFK"
        assert created_route.id is not None
        assert created_route.createdAt is not None
        assert created_route.updatedAt is not None

        # Verify it was persisted
        persisted = session.query(RouteModel).filter(
            RouteModel.id == created_route.id
        ).first()
        assert persisted is not None
        assert persisted.flightId == "AA123"

    def test_create_route_generates_uuid(self, repository, valid_route):
        """Test that route gets a UUID if not provided."""
        valid_route.id = None
        created_route = repository.create(valid_route)

        assert created_route.id is not None
        assert len(created_route.id) == 36  # UUID length

    def test_create_route_duplicate_flight_id(self, repository, valid_route, session):
        """Test that duplicate flightId raises error."""
        # Create first route
        route1 = repository.create(valid_route)

        # Try to create second route with same flightId
        valid_route.flightId = "AA123"
        valid_route.id = None

        with pytest.raises(RouteAlreadyExistsError, match="already exists"):
            repository.create(valid_route)

    def test_create_route_invalid_dates(self, repository):
        """Test that invalid dates are rejected."""
        future_start = datetime.utcnow() + timedelta(days=1)
        future_end = future_start - timedelta(hours=12)  # End before start

        route = Route(
            flightId="AA123",
            sourceAirportCode="JFK",
            sourceCountry="USA",
            destinyAirportCode="MIA",
            destinyCountry="USA",
            bagCost=50,
            plannedStartDate=future_start,
            plannedEndDate=future_end,
        )

        with pytest.raises(ValueError, match="must be after start date"):
            repository.create(route)

    def test_create_route_end_before_start(self, repository):
        """Test that end before start is rejected."""
        start_date = datetime.utcnow() + timedelta(days=1)
        end_date = start_date - timedelta(hours=12)  # Before start

        route = Route(
            flightId="AA123",
            sourceAirportCode="JFK",
            sourceCountry="USA",
            destinyAirportCode="MIA",
            destinyCountry="USA",
            bagCost=50,
            plannedStartDate=start_date,
            plannedEndDate=end_date,
        )

        with pytest.raises(ValueError, match="must be after start date"):
            repository.create(route)

    def test_get_by_id_success(self, repository, valid_route, session):
        """Test getting a route by id."""
        created = repository.create(valid_route)
        retrieved = repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.flightId == created.flightId

    def test_get_by_id_not_found(self, repository):
        """Test getting a non-existent route."""
        result = repository.get_by_id("non-existent-id")
        assert result is None

    def test_get_by_flight_id_success(self, repository, valid_route, session):
        """Test getting a route by flightId."""
        created = repository.create(valid_route)
        retrieved = repository.get_by_flight_id("AA123")

        assert retrieved is not None
        assert retrieved.flightId == "AA123"

    def test_get_by_flight_id_not_found(self, repository):
        """Test getting a route by flightId that doesn't exist."""
        result = repository.get_by_flight_id("NONEXISTENT")
        assert result is None

    def test_list_routes_success(self, repository, valid_route, session):
        """Test listing all routes."""
        # Create two routes
        route1 = repository.create(valid_route)

        valid_route2 = Route(
            flightId="AA456",
            sourceAirportCode="LAX",
            sourceCountry="USA",
            destinyAirportCode="SFO",
            destinyCountry="USA",
            bagCost=100,
            plannedStartDate=valid_route.plannedStartDate,
            plannedEndDate=valid_route.plannedEndDate,
        )
        route2 = repository.create(valid_route2)

        routes = repository.list_routes()

        assert len(routes) == 2
        flight_ids = [r.flightId for r in routes]
        assert "AA123" in flight_ids
        assert "AA456" in flight_ids

    def test_delete_route_success(self, repository, valid_route, session):
        """Test deleting a route."""
        created = repository.create(valid_route)
        result = repository.delete(created)

        assert result is True
        retrieved = repository.get_by_id(created.id)
        assert retrieved is None

    def test_delete_route_not_found(self, repository, session):
        """Test deleting a non-existent route."""
        from domain.models.route import Route
        from datetime import timedelta

        # Create a route without id
        future_start = datetime.utcnow() + timedelta(days=1)
        future_end = future_start + timedelta(days=1)

        route_without_id = Route(
            flightId="NONEXISTENT",
            sourceAirportCode="JFK",
            sourceCountry="USA",
            destinyAirportCode="MIA",
            destinyCountry="USA",
            bagCost=50,
            plannedStartDate=future_start,
            plannedEndDate=future_end,
            id=None,
        )

        # Should raise ValueError when trying to delete without id
        with pytest.raises(ValueError, match="without id"):
            repository.delete(route_without_id)

    def test_delete_route_without_id(self, repository):
        """Test that deleting without id raises error."""
        route = Route(
            flightId="AA123",
            sourceAirportCode="JFK",
            sourceCountry="USA",
            destinyAirportCode="MIA",
            destinyCountry="USA",
            bagCost=50,
            plannedStartDate=datetime.utcnow() + timedelta(days=1),
            plannedEndDate=datetime.utcnow() + timedelta(days=2),
            id=None,
        )

        with pytest.raises(ValueError, match="without id"):
            repository.delete(route)

    def test_count_routes_success(self, repository, valid_route, session):
        """Test counting routes."""
        # Create two routes
        repository.create(valid_route)

        valid_route2 = Route(
            flightId="AA456",
            sourceAirportCode="LAX",
            sourceCountry="USA",
            destinyAirportCode="SFO",
            destinyCountry="USA",
            bagCost=100,
            plannedStartDate=valid_route.plannedStartDate,
            plannedEndDate=valid_route.plannedEndDate,
        )
        repository.create(valid_route2)

        count = repository.count()
        assert count == 2

    def test_count_routes_empty(self, repository):
        """Test counting when repository is empty."""
        count = repository.count()
        assert count == 0

    def test_delete_all_routes(self, repository, valid_route, session):
        """Test deleting all routes."""
        # Create two routes
        repository.create(valid_route)

        valid_route2 = Route(
            flightId="AA456",
            sourceAirportCode="LAX",
            sourceCountry="USA",
            destinyAirportCode="SFO",
            destinyCountry="USA",
            bagCost=100,
            plannedStartDate=valid_route.plannedStartDate,
            plannedEndDate=valid_route.plannedEndDate,
        )
        repository.create(valid_route2)

        # Delete all
        repository.delete_all()

        # Verify all deleted
        assert repository.count() == 0
        assert repository.list_routes() == []

    def test_create_route_with_existing_id(self, repository, valid_route, session):
        """Test creating a route with explicit id."""
        valid_route.id = "550e8400-e29b-41d4-a716-446655440000"
        created = repository.create(valid_route)

        assert created.id == "550e8400-e29b-41d4-a716-446655440000"

        # Verify it was persisted with that id
        retrieved = repository.get_by_id("550e8400-e29b-41d4-a716-446655440000")
        assert retrieved is not None

    def test_get_by_id_with_past_dates(self, repository, session):
        """Test that get_by_id can retrieve routes with past dates.

        This verifies the fix for issue #66 where past dates would cause
        validation errors when converting SQLAlchemy models to domain models.
        """
        # Directly insert a route with past dates into the database,
        # bypassing the normal validation layer
        past_start = datetime.utcnow() - timedelta(days=30)
        past_end = past_start + timedelta(hours=2)

        past_route = RouteModel(
            id="550e8400-e29b-41d4-a716-446655440001",
            flightId="AA123",
            sourceAirportCode="JFK",
            sourceCountry="United States",
            destinyAirportCode="MIA",
            destinyCountry="United States",
            bagCost=50,
            plannedStartDate=past_start,
            plannedEndDate=past_end,
            createdAt=past_start,
            updatedAt=past_end,
        )
        session.add(past_route)
        session.commit()

        # Retrieve the route using get_by_id which calls to_route()
        retrieved = repository.get_by_id("550e8400-e29b-41d4-a716-446655440001")

        # Should successfully load the route despite past dates
        assert retrieved is not None
        assert retrieved.id == "550e8400-e29b-41d4-a716-446655440001"
        assert retrieved.flightId == "AA123"
        assert retrieved.plannedStartDate == past_start
        assert retrieved.plannedEndDate == past_end
        # Verify the past dates are preserved correctly
        assert retrieved.plannedStartDate < datetime.utcnow()

    def test_list_routes_with_past_dates(self, repository, session):
        """Test that list_routes can retrieve routes with past dates.

        This verifies the fix for issue #66 where past dates would cause
        validation errors when converting SQLAlchemy models to domain models.
        """
        # Directly insert routes with past dates into the database
        past_start = datetime.utcnow() - timedelta(days=30)

        past_route1 = RouteModel(
            id="550e8400-e29b-41d4-a716-446655440002",
            flightId="AA456",
            sourceAirportCode="LAX",
            sourceCountry="USA",
            destinyAirportCode="SFO",
            destinyCountry="USA",
            bagCost=75,
            plannedStartDate=past_start,
            plannedEndDate=past_start + timedelta(hours=2),
            createdAt=past_start,
            updatedAt=past_start + timedelta(hours=2),
        )
        past_route2 = RouteModel(
            id="550e8400-e29b-41d4-a716-446655440003",
            flightId="AA789",
            sourceAirportCode="JFK",
            sourceCountry="USA",
            destinyAirportCode="BOS",
            destinyCountry="USA",
            bagCost=100,
            plannedStartDate=past_start + timedelta(days=5),
            plannedEndDate=past_start + timedelta(days=6),
            createdAt=past_start + timedelta(days=5),
            updatedAt=past_start + timedelta(days=6),
        )
        session.add_all([past_route1, past_route2])
        session.commit()

        # Also add a future date route
        future_start = datetime.utcnow() + timedelta(days=1)
        future_route = repository.create(
            Route(
                flightId="AA999",
                sourceAirportCode="MIA",
                sourceCountry="USA",
                destinyAirportCode="ORD",
                destinyCountry="USA",
                bagCost=60,
                plannedStartDate=future_start,
                plannedEndDate=future_start + timedelta(days=1),
            )
        )

        # Retrieve all routes - should include both past and future date routes
        all_routes = repository.list_routes()

        assert len(all_routes) == 3
        flight_ids = [r.flightId for r in all_routes]
        assert "AA456" in flight_ids
        assert "AA789" in flight_ids
        assert "AA999" in flight_ids

        # Verify past date routes still have their dates preserved
        past_route = next(r for r in all_routes if r.flightId == "AA456")
        assert past_route.plannedStartDate < datetime.utcnow()
