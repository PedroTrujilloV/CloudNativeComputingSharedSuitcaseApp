from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PackageSize(str, Enum):
    LARGE = "LARGE"
    MEDIUM = "MEDIUM"
    SMALL = "SMALL"


class Offer(BaseModel):
    id: UUID
    post_id: UUID
    user_id: UUID
    description: str = Field(min_length=1, description="Description cannot be empty")
    size: PackageSize
    fragile: bool
    offer: Decimal
    created_at: datetime


class OfferCreateRequest(BaseModel):
    """Schema-only model: only validates presence and basic types.

    Domain rules (valid size, non-negative amount, decimal precision, max
    description length) are enforced in the use case and return HTTP 412.
    """

    post_id: UUID = Field(alias="postId")
    user_id: UUID = Field(alias="userId")
    description: str = Field(
        min_length=1,
        description="Description cannot be empty",
    )
    size: str  # validated as domain rule (LARGE/MEDIUM/SMALL) in use case → 412
    fragile: bool
    offer: Decimal


class OfferCreateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    user_id: UUID = Field(alias="userId")
    created_at: datetime = Field(alias="createdAt")


class OfferResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    post_id: UUID = Field(alias="postId")
    user_id: UUID = Field(alias="userId")
    description: str
    size: PackageSize
    fragile: bool
    offer: Decimal
    created_at: datetime = Field(alias="createdAt")
