"""Pydantic schemas for request/response validation."""
from datetime import datetime

from pydantic import BaseModel, Field


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


class RouteCreateResponse(BaseModel):
    """Response body for successful route creation."""

    id: str
    createdAt: datetime


class RouteErrorResponse(BaseModel):
    """Common error response schema."""

    msg: str