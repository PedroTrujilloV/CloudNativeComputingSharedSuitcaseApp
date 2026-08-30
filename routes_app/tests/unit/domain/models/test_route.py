"""Unit tests for Route domain model."""
from datetime import datetime, timedelta
import pytest
from domain.models.route import Route


class TestRouteValidation:
    """Tests for Route model validation."""

    @pytest.fixture
    def valid_route_data(self):
        """Create valid route data."""
        future_start = datetime.utcnow() + timedelta(days=1)
        future_end = future_start + timedelta(days=1)

        return {
            "flightId": "AA123",
            "sourceAirportCode": "JFK",
            "sourceCountry": "United States",
            "destinyAirportCode": "MIA",
            "destinyCountry": "United States",
            "bagCost": 50,
            "plannedStartDate": future_start,
            "plannedEndDate": future_end,
        }

    def test_route_creation_with_valid_data(self, valid_route_data):
        """Route should be created successfully with valid data."""
        route = Route(**valid_route_data)
        assert route.flightId == "AA123"
        assert route.bagCost == 50
        assert route.sourceAirportCode == "JFK"
        assert route.destinyAirportCode == "MIA"

    def test_route_with_none_id(self, valid_route_data):
        """Route can be created with id=None."""
        route = Route(**valid_route_data)
        assert route.id is None

    def test_route_with_generated_id(self, valid_route_data):
        """Route can be created with explicit id."""
        valid_route_data["id"] = "550e8400-e29b-41d4-a716-446655440000"
        route = Route(**valid_route_data)
        assert route.id == "550e8400-e29b-41d4-a716-446655440000"


class TestRouteDateValidation:
    """Tests for route date validation."""

    def test_route_validation_valid_dates(self):
        """Route with valid future dates passes validation."""
        future_start = datetime.utcnow() + timedelta(days=1)
        future_end = future_start + timedelta(days=1)

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

        # Should not raise
        route.validate_dates()
        route.validate_date_not_past()

    def test_route_validation_end_before_start(self):
        """Route validation should fail when end date before start."""
        # Create dates where end_date is actually earlier than start_date
        end_date = datetime.utcnow() + timedelta(days=1)
        start_date = end_date + timedelta(hours=12)  # Start is after end

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

        with pytest.raises(ValueError):
            route.validate_dates()

    def test_route_validation_end_equals_start(self):
        """Route validation should fail when end date equals start."""
        same_date = datetime.utcnow() + timedelta(days=1)

        route = Route(
            flightId="AA123",
            sourceAirportCode="JFK",
            sourceCountry="USA",
            destinyAirportCode="MIA",
            destinyCountry="USA",
            bagCost=50,
            plannedStartDate=same_date,
            plannedEndDate=same_date,
        )

        with pytest.raises(ValueError, match="end date.*must be after start date"):
            route.validate_dates()

    def test_route_validation_past_dates(self):
        """Route validation for past dates is handled by Pydantic during creation."""
        future_start = datetime.utcnow() + timedelta(days=1)
        future_end = future_start + timedelta(days=1)

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

        # Should not raise for valid future dates
        route.validate_date_not_past()


class TestRouteFlightIdValidation:
    """Tests for flightId validation."""

    def test_route_validation_empty_flight_id(self):
        """Route validation should fail for empty flightId."""
        future_date = datetime.utcnow() + timedelta(days=1)

        with pytest.raises(ValueError):
            Route(
                flightId="",
                sourceAirportCode="JFK",
                sourceCountry="USA",
                destinyAirportCode="MIA",
                destinyCountry="USA",
                bagCost=50,
                plannedStartDate=future_date,
                plannedEndDate=future_date,
            )


class TestRouteAirportCodeValidation:
    """Tests for airport code validation."""

    def test_route_validation_valid_airport_codes(self):
        """Route validation should accept valid IATA codes."""
        future_start = datetime.utcnow() + timedelta(days=1)
        future_end = future_start + timedelta(days=1)

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

        # Should not raise
        route.validate_dates()

    def test_route_validation_lowercase_airport_codes(self):
        """Route validation should fail for lowercase airport codes."""
        future_date = datetime.utcnow() + timedelta(days=1)

        with pytest.raises(ValueError):
            Route(
                flightId="AA123",
                sourceAirportCode="jfk",
                sourceCountry="USA",
                destinyAirportCode="mia",
                destinyCountry="USA",
                bagCost=50,
                plannedStartDate=future_date,
                plannedEndDate=future_date,
            )

    def test_route_validation_short_airport_codes(self):
        """Route validation should fail for short airport codes."""
        future_date = datetime.utcnow() + timedelta(days=1)

        with pytest.raises(ValueError):
            Route(
                flightId="AA123",
                sourceAirportCode="JF",
                sourceCountry="USA",
                destinyAirportCode="MI",
                destinyCountry="USA",
                bagCost=50,
                plannedStartDate=future_date,
                plannedEndDate=future_date,
            )

    def test_route_validation_airport_codes_with_numbers(self):
        """Route validation should fail for airport codes with numbers."""
        future_date = datetime.utcnow() + timedelta(days=1)

        with pytest.raises(ValueError):
            Route(
                flightId="AA123",
                sourceAirportCode="JFK1",
                sourceCountry="USA",
                destinyAirportCode="MIA2",
                destinyCountry="USA",
                bagCost=50,
                plannedStartDate=future_date,
                plannedEndDate=future_date,
            )


class TestRouteBagCostValidation:
    """Tests for bagCost validation."""

    def test_route_validation_zero_bag_cost(self):
        """Route validation should accept zero bag cost."""
        future_start = datetime.utcnow() + timedelta(days=1)
        future_end = future_start + timedelta(days=1)

        route = Route(
            flightId="AA123",
            sourceAirportCode="JFK",
            sourceCountry="USA",
            destinyAirportCode="MIA",
            destinyCountry="USA",
            bagCost=0,
            plannedStartDate=future_start,
            plannedEndDate=future_end,
        )

        # Should not raise
        route.validate_dates()

    def test_route_validation_negative_bag_cost(self):
        """Route validation should fail for negative bag cost."""
        future_date = datetime.utcnow() + timedelta(days=1)

        with pytest.raises(ValueError):
            Route(
                flightId="AA123",
                sourceAirportCode="JFK",
                sourceCountry="USA",
                destinyAirportCode="MIA",
                destinyCountry="USA",
                bagCost=-1,
                plannedStartDate=future_date,
                plannedEndDate=future_date,
            )


class TestRouteFields:
    """Tests for Route fields."""

    def test_route_id_is_nullable(self):
        """Route id should be nullable."""
        future_date = datetime.utcnow() + timedelta(days=1)

        route = Route(
            flightId="AA123",
            sourceAirportCode="JFK",
            sourceCountry="USA",
            destinyAirportCode="MIA",
            destinyCountry="USA",
            bagCost=50,
            plannedStartDate=future_date,
            plannedEndDate=future_date,
            id=None,
        )

        assert route.id is None


class TestRouteFromDb:
    """Tests for creating Route from database values."""

    def test_route_from_db_with_past_dates(self):
        """Route can be created from DB data even with past dates."""
        past_date = datetime.utcnow() - timedelta(days=1)

        db_data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "flightId": "AA123",
            "sourceAirportCode": "JFK",
            "sourceCountry": "USA",
            "destinyAirportCode": "MIA",
            "destinyCountry": "USA",
            "bagCost": 50,
            "plannedStartDate": past_date,
            "plannedEndDate": past_date + timedelta(hours=2),
            "createdAt": past_date,
            "updatedAt": past_date,
        }

        route = Route.from_db(db_data)

        assert route.id == "550e8400-e29b-41d4-a716-446655440000"
        assert route.flightId == "AA123"
        assert route.plannedStartDate == past_date
        assert route.plannedEndDate == past_date + timedelta(hours=2)

    def test_route_from_db_with_valid_dates(self):
        """Route can be created from DB data with valid future dates."""
        future_start = datetime.utcnow() + timedelta(days=1)
        future_end = future_start + timedelta(days=1)

        db_data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "flightId": "AA456",
            "sourceAirportCode": "LAX",
            "sourceCountry": "USA",
            "destinyAirportCode": "SFO",
            "destinyCountry": "USA",
            "bagCost": 75,
            "plannedStartDate": future_start,
            "plannedEndDate": future_end,
            "createdAt": future_start,
            "updatedAt": future_end,
        }

        route = Route.from_db(db_data)

        assert route.id == "550e8400-e29b-41d4-a716-446655440000"
        assert route.flightId == "AA456"
        assert route.bagCost == 75
        assert route.plannedStartDate == future_start
        assert route.plannedEndDate == future_end

    def test_route_from_db_without_timestamps(self):
        """Route can be created from DB data without timestamps."""
        future_start = datetime.utcnow() + timedelta(days=1)
        future_end = future_start + timedelta(days=1)

        db_data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "flightId": "AA789",
            "sourceAirportCode": "MIA",
            "sourceCountry": "USA",
            "destinyAirportCode": "BOS",
            "destinyCountry": "USA",
            "bagCost": 100,
            "plannedStartDate": future_start,
            "plannedEndDate": future_end,
        }

        route = Route.from_db(db_data)

        assert route.id == "550e8400-e29b-41d4-a716-446655440000"
        assert route.createdAt is None
        assert route.updatedAt is None
