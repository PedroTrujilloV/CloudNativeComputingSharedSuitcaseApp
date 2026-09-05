"""API schemas for the RF-004 create-offer request.

The request body mirrors the official RF-004 contract: ``description``,
``size`` (LARGE, MEDIUM or SMALL), ``fragile`` and ``offer``. All fields
are required, so a missing or malformed field fails the HTTP 400 gate
before any downstream call is made.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RF004CreateOfferRequest(BaseModel):
    """Request body for POST /rf004/posts/{post_id}/offers."""

    model_config = ConfigDict(populate_by_name=True)

    description: str = Field(..., min_length=1, description="Offer description")
    size: Literal["LARGE", "MEDIUM", "SMALL"] = Field(
        ..., description="Baggage size category"
    )
    fragile: bool = Field(..., description="Whether the baggage is fragile")
    offer: float = Field(..., ge=0, description="Offered price")
