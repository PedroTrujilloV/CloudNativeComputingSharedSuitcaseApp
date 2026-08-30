"""Unit tests for Route validation services."""
from datetime import datetime, timedelta
import pytest
from domain.services.route_validation import validate_route_dates, validate_route_data


class TestValidateRouteDates:
    """Tests for validate_route_dates function."""

    def test_validate_dates_valid(self):
        """Validation should pass for valid future dates."""
        start_date = datetime.utcnow() + timedelta(days=1)
        end_date = start_date + timedelta(days=1)

        # Should not raise
        validate_route_dates(start_date, end_date)

    def test_validate_dates_end_before_start(self):
        """Validation should fail when end date before start."""
        start_date = datetime.utcnow() + timedelta(days=1)
        end_date = datetime.utcnow() + timedelta(hours=12)  # Before start

        with pytest.raises(ValueError, match="end date.*must be after start date"):
            validate_route_dates(start_date, end_date)

    def test_validate_dates_end_equals_start(self):
        """Validation should fail when end date equals start."""
        same_date = datetime.utcnow() + timedelta(days=1)

        with pytest.raises(ValueError, match="end date.*must be after start date"):
            validate_route_dates(same_date, same_date)

    def test_validate_dates_past_start_date(self):
        """Validation should fail when start date is in the past."""
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow() + timedelta(days=1)

        with pytest.raises(ValueError, match="is in the past"):
            validate_route_dates(start_date, end_date)

    def test_validate_dates_past_end_date(self):
        """Validation should fail when end date is in the past."""
        start_date = datetime.utcnow() + timedelta(days=1)
        end_date = datetime.utcnow() - timedelta(days=1)

        with pytest.raises(ValueError, match="is in the past"):
            validate_route_dates(start_date, end_date)

    def test_validate_dates_both_past_dates(self):
        """Validation should fail when both dates are in the past."""
        start_date = datetime.utcnow() - timedelta(days=2)
        end_date = datetime.utcnow() - timedelta(days=1)

        with pytest.raises(ValueError, match="is in the past"):
            validate_route_dates(start_date, end_date)

    def test_validate_dates_consecutive_days(self):
        """Validation should pass for consecutive days."""
        start_date = datetime.utcnow() + timedelta(days=1)
        end_date = start_date + timedelta(days=1)

        # Should not raise
        validate_route_dates(start_date, end_date)


class TestValidateRouteData:
    """Tests for validate_route_data function."""

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

    def test_validate_data_valid(self, valid_route_data):
        """Validation should pass for valid route data."""
        # Should not raise
        validate_route_data(valid_route_data)

    def test_validate_data_missing_flight_id(self, valid_route_data):
        """Validation should fail when flightId is missing."""
        missing_flight_id = valid_route_data.copy()
        del missing_flight_id["flightId"]

        with pytest.raises(ValueError, match="Missing required field: flightId"):
            validate_route_data(missing_flight_id)

    def test_validate_data_missing_airport_codes(self, valid_route_data):
        """Validation should fail when airport codes are missing."""
        missing_airport = valid_route_data.copy()
        del missing_airport["sourceAirportCode"]

        with pytest.raises(ValueError, match="Missing required field: sourceAirportCode"):
            validate_route_data(missing_airport)

    def test_validate_data_missing_bag_cost(self, valid_route_data):
        """Validation should fail when bagCost is missing."""
        missing_cost = valid_route_data.copy()
        del missing_cost["bagCost"]

        with pytest.raises(ValueError, match="Missing required field: bagCost"):
            validate_route_data(missing_cost)

    def test_validate_data_empty_flight_id(self, valid_route_data):
        """Validation should fail for empty flightId."""
        empty_flight_id = valid_route_data.copy()
        empty_flight_id["flightId"] = ""

        with pytest.raises(ValueError, match="flightId cannot be empty"):
            validate_route_data(empty_flight_id)

    def test_validate_data_whitespace_flight_id(self, valid_route_data):
        """Validation should fail for whitespace-only flightId."""
        whitespace_flight_id = valid_route_data.copy()
        whitespace_flight_id["flightId"] = "   "

        with pytest.raises(ValueError, match="flightId cannot be empty"):
            validate_route_data(whitespace_flight_id)

    def test_validate_data_invalid_airport_codes_lowercase(self, valid_route_data):
        """Validation should fail for lowercase airport codes."""
        invalid_codes = valid_route_data.copy()
        invalid_codes["sourceAirportCode"] = "jfk"
        invalid_codes["destinyAirportCode"] = "mia"

        with pytest.raises(ValueError, match="Invalid airport code format"):
            validate_route_data(invalid_codes)

    def test_validate_data_invalid_airport_codes_short(self, valid_route_data):
        """Validation should fail for short airport codes."""
        short_codes = valid_route_data.copy()
        short_codes["sourceAirportCode"] = "JF"
        short_codes["destinyAirportCode"] = "MI"

        with pytest.raises(ValueError, match="Invalid airport code format"):
            validate_route_data(short_codes)

    def test_validate_data_negative_bag_cost(self, valid_route_data):
        """Validation should fail for negative bag cost."""
        negative_cost = valid_route_data.copy()
        negative_cost["bagCost"] = -50

        with pytest.raises(ValueError, match="bagCost must be a non-negative"):
            validate_route_data(negative_cost)

    def test_validate_data_past_start_date(self, valid_route_data):
        """Validation should fail for past start date."""
        past_dates = valid_route_data.copy()
        past_dates["plannedStartDate"] = datetime.utcnow() - timedelta(days=1)
        past_dates["plannedEndDate"] = datetime.utcnow() + timedelta(days=1)

        with pytest.raises(ValueError, match="is in the past"):
            validate_route_data(past_dates)

    def test_validate_data_end_before_start(self, valid_route_data):
        """Validation should fail when end date before start."""
        invalid_dates = valid_route_data.copy()
        invalid_dates["plannedEndDate"] = datetime.utcnow() + timedelta(hours=12)
        invalid_dates["plannedStartDate"] = datetime.utcnow() + timedelta(days=1)

        with pytest.raises(ValueError, match="must be after start date"):
            validate_route_data(invalid_dates)
