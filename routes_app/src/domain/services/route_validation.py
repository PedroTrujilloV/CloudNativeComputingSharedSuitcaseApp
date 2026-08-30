"""Route validation logic."""
from datetime import datetime, timezone


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def validate_route_dates(planned_start_date: datetime, planned_end_date: datetime) -> None:
    """Validate that route dates are valid.

    Args:
        planned_start_date: The start date of the journey.
        planned_end_date: The end date of the journey.

    Raises:
        ValueError: If dates are invalid (past dates or end before start).
    """
    now = datetime.now(timezone.utc)

    start = _ensure_utc(planned_start_date)
    end = _ensure_utc(planned_end_date)

    # Check if dates are in the past
    if start < now:
        raise ValueError("Planned start date is in the past")
    if end < now:
        raise ValueError("Planned end date is in the past")

    # Check if end date is after start date
    if end <= start:
        raise ValueError(
            "Planned end date must be after start date"
        )


def validate_route_data(route_data: dict) -> None:
    """Validate route data from request.

    Args:
        route_data: Dictionary containing route data from request.

    Raises:
        ValueError: If any field is invalid.
    """
    # Validate required fields
    required_fields = [
        "flightId",
        "sourceAirportCode",
        "sourceCountry",
        "destinyAirportCode",
        "destinyCountry",
        "bagCost",
        "plannedStartDate",
        "plannedEndDate",
    ]

    for field in required_fields:
        if field not in route_data or route_data[field] is None:
            raise ValueError(f"Missing required field: {field}")

    # Validate flightId is not empty
    if not route_data["flightId"] or not str(route_data["flightId"]).strip():
        raise ValueError("flightId cannot be empty")

    # Validate airport codes format (3 uppercase letters)
    import re

    for field in ["sourceAirportCode", "destinyAirportCode"]:
        if not re.match(r"^[A-Z]{3}$", str(route_data[field])):
            raise ValueError(
                f"Invalid airport code format for {field}: "
                f"{route_data[field]}. Must be 3 uppercase letters."
            )

    # Validate bagCost is non-negative
    if route_data["bagCost"] < 0:
        raise ValueError("bagCost must be a non-negative integer")

    # Validate dates
    planned_start = route_data["plannedStartDate"]
    planned_end = route_data["plannedEndDate"]

    if planned_start < datetime.utcnow():
        raise ValueError(f"Planned start date {planned_start} is in the past")
    if planned_end < datetime.utcnow():
        raise ValueError(f"Planned end date {planned_end} is in the past")
    if planned_end <= planned_start:
        raise ValueError(
            f"Planned end date ({planned_end}) must be after start date ({planned_start})"
        )
