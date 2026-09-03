"""API schemas for the RF-003 create-post request.

The request body mirrors the fields the route/post creation stage will need
(``routes_app``'s ``RouteCreateRequest`` plus the post ``expireAt``). Only the
required/malformed-field gate (HTTP 400) is in scope for this task; the values
are forwarded to the next stage as-is.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Airport(BaseModel):
    """Origin or destiny airport block."""

    model_config = ConfigDict(populate_by_name=True)

    airportCode: str = Field(
        ..., min_length=3, max_length=3, description="IATA airport code"
    )
    country: str = Field(..., min_length=1, description="Country name")


class RF003CreatePostRequest(BaseModel):
    """Request body for POST /rf003/posts."""

    model_config = ConfigDict(populate_by_name=True)

    flightId: str = Field(..., min_length=1, description="Flight identifier")
    expireAt: datetime = Field(
        ..., description="Post expiration date and time (ISO 8601, UTC)"
    )
    plannedStartDate: datetime = Field(
        ..., description="Journey start date and time (ISO 8601, UTC)"
    )
    plannedEndDate: datetime = Field(
        ..., description="Journey end date and time (ISO 8601, UTC)"
    )
    origin: Airport = Field(..., description="Origin airport block")
    destiny: Airport = Field(..., description="Destiny airport block")
    bagCost: int = Field(..., ge=0, description="Baggage shipping cost")
