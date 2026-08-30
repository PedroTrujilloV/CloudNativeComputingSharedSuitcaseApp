from datetime import datetime, timezone
import re

from pydantic import BaseModel, Field, field_validator


class Route(BaseModel):
    """Route(Trayecto) domain model representing a journey between airports."""

    id: str | None = None
    flightId: str = Field(..., min_length=1, description="Flight identifier (e.g., AA001)")
    sourceAirportCode: str = Field(..., min_length=3, max_length=3, description="Origin airport IATA code")
    sourceCountry: str = Field(..., min_length=1, description="Country of origin")
    destinyAirportCode: str = Field(..., min_length=3, max_length=3, description="Destination airport IATA code")
    destinyCountry: str = Field(..., min_length=1, description="Destination country")
    bagCost: int = Field(..., ge=0, description="Cost of shipping a suitcase on the journey")
    plannedStartDate: datetime = Field(..., description="Planned start date and time of the journey")
    plannedEndDate: datetime = Field(..., description="Planned end date and time of the journey")
    createdAt: datetime | None = None
    updatedAt: datetime | None = None

    @field_validator("plannedStartDate", "plannedEndDate")
    @classmethod
    def validate_future_date(cls, v: datetime) -> datetime:
        """Normalize timezone-aware datetimes for UTC.

        Date validity checks are deferred to the router layer.
        """
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("flightId")
    @classmethod
    def validate_flight_id_not_null(cls, v: str) -> str:
        """Ensure flightId is not empty."""
        if not v or v.strip() == "":
            raise ValueError("flightId cannot be empty")
        return v

    @field_validator("sourceAirportCode", "destinyAirportCode")
    @classmethod
    def validate_airport_codes(cls, v: str) -> str:
        """Ensure airport codes are valid IATA format (3 uppercase letters)."""
        import re
        if not re.match(r"^[A-Z]{3}$", v):
            raise ValueError(f"Invalid airport code format: {v}. Must be 3 uppercase letters.")
        return v

    def validate_dates(self) -> None:
        """Validate that start date is before end date."""
        if self.plannedEndDate <= self.plannedStartDate:
            raise ValueError(
                f"Planned end date ({self.plannedEndDate}) must be after start date ({self.plannedStartDate})"
            )

    def validate_date_not_past(self) -> None:
        """Validate that planned dates are not in the past."""
        now = datetime.now(timezone.utc)
        # Handle both offset-aware and offset-naive datetimes
        start_date = self.plannedStartDate
        end_date = self.plannedEndDate
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        if start_date < now:
            raise ValueError(f"Planned start date {self.plannedStartDate} is in the past")
        if end_date < now:
            raise ValueError(f"Planned end date {self.plannedEndDate} is in the past")

    @classmethod
    def from_db(cls, data: dict) -> "Route":
        """Create a Route from database values without past-date validation.

        This is used when hydrating domain objects from the database,
        where the "not in the past" rule may no longer apply.

        Args:
            data: Dictionary containing route data from database.

        Returns:
            A new Route instance without future-date validation.
        """
        return cls.model_construct(
            id=data.get("id"),
            flightId=data["flightId"],
            sourceAirportCode=data["sourceAirportCode"],
            sourceCountry=data["sourceCountry"],
            destinyAirportCode=data["destinyAirportCode"],
            destinyCountry=data["destinyCountry"],
            bagCost=data["bagCost"],
            plannedStartDate=data["plannedStartDate"],
            plannedEndDate=data["plannedEndDate"],
            createdAt=data.get("createdAt"),
            updatedAt=data.get("updatedAt"),
        )


# Pydantic schemas for request/response validation
class RouteCreateRequest(BaseModel):
    """Request body for creating a new route."""

    flightId: str = Field(..., min_length=1, description="Flight identifier")
    sourceAirportCode: str = Field(..., min_length=3, max_length=3, description="Origin airport IATA code")
    sourceCountry: str = Field(..., min_length=1, description="Origin country name")
    destinyAirportCode: str = Field(..., min_length=3, max_length=3, description="Destination airport IATA code")
    destinyCountry: str = Field(..., min_length=1, description="Destination country name")
    bagCost: int = Field(..., ge=0, description="Baggage shipping cost")
    plannedStartDate: datetime = Field(..., description="Journey start date and time in ISO format (UTC)")
    plannedEndDate: datetime = Field(..., description="Journey end date and time in ISO format (UTC)")

    @field_validator("sourceAirportCode", "destinyAirportCode")
    @classmethod
    def validate_airport_codes(cls, v: str) -> str:
        """Ensure airport codes are valid IATA format (3 uppercase letters)."""
        if not re.match(r"^[A-Z]{3}$", v):
            raise ValueError(f"Invalid airport code format: {v}. Must be 3 uppercase letters.")
        return v

    @field_validator("plannedStartDate", "plannedEndDate")
    @classmethod
    def validate_future_date(cls, v: datetime) -> datetime:
        """Normalize timezone-aware datetimes for UTC.

        Date validity checks (past dates, consecutiveness) are deferred
        to the router layer so that HTTP 412 status codes can be returned
        per API contract rather than Pydantic's 422.
        """
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("flightId")
    @classmethod
    def validate_flight_id_not_null(cls, v: str) -> str:
        """Ensure flightId is not empty."""
        if not v or v.strip() == "":
            raise ValueError("flightId cannot be empty")
        return v


class RouteCreateResponse(BaseModel):
    """Response body for successful route creation."""

    id: str
    createdAt: datetime


class RouteErrorResponse(BaseModel):
    """Common error response schema."""

    msg: str
