from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Score(BaseModel):
    """Domain model for the Utilidad (Score) entity.

    Links a computed score value to an offer so it can be retrieved later
    even if it changes over time. A missing score for an offer is represented
    by the absence of a row (callers read it as ``score: null``), never by a
    zero or sentinel value.

    The value is the result of the Entrega 1 glossary formula
    (``utilidad = offer amount - (bag occupancy % x route bagCost)``,
    occupancy 100%/50%/25% for LARGE/MEDIUM/SMALL), computed by the RF-004
    orchestrator and persisted here as a plain number.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Score identifier (UUID string)",
    )
    offer_id: str = Field(
        description="Identifier of the offer this score belongs to (UUID string)"
    )
    value: float = Field(description="Computed utility value (utilidad)")
    created_at: datetime = Field(description="Creation timestamp (UTC)")
    updated_at: datetime = Field(description="Last update timestamp (UTC)")


class ScoreCreateRequest(BaseModel):
    """API request schema for creating/updating a score (RF-004).

    The API contract uses the camelCase field ``offerId`` and the numeric
    field ``score`` (the domain field is ``value``). Missing or malformed
    fields are rejected with HTTP 400 by FastAPI validation.
    """

    offer_id: UUID = Field(alias="offerId")
    score: float


class ScoreCreateResponse(BaseModel):
    """API response after creating a score (HTTP 201)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    offer_id: UUID = Field(alias="offerId")
    score: float
    created_at: datetime = Field(alias="createdAt")


class ScoreUpdateResponse(BaseModel):
    """API response after updating an existing score (HTTP 200)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    offer_id: UUID = Field(alias="offerId")
    score: float
    updated_at: datetime = Field(alias="updatedAt")


class ScoreGetResponse(BaseModel):
    """API response for GET /scores?offerId (RF-005).

    Null-safe: when the offer has no score yet, ``score`` is ``null`` and
    ``id`` / ``createdAt`` are omitted (the endpoint still returns 200).
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    offer_id: UUID = Field(alias="offerId")
    score: float | None = None
    created_at: datetime | None = Field(default=None, alias="createdAt")

    def model_dump(self, **kwargs):
        """Serialize without the fields that are absent for this payload."""
        data = super().model_dump(**kwargs)
        if self.id is None:
            data.pop("id", None)
        if self.created_at is None:
            data.pop("createdAt", None)
        return data


class ScoreFullResponse(BaseModel):
    """API response for GET /scores/{id} with all persisted fields."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    offer_id: UUID = Field(alias="offerId")
    score: float
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
