from enum import Enum

from pydantic import BaseModel, Field


class PetType(str, Enum):
    """Enum for pet types."""

    DOG = "dog"
    CAT = "cat"
    BIRD = "bird"
    OTHER = "other"


class Pet(BaseModel):
    """Pet domain model."""

    id: int | None = None
    name: str = Field(min_length=1, description="Name cannot be empty")
    type: PetType
    age: int = Field(gt=0, description="Age must be greater than 0")
    owner_name: str = Field(min_length=1, description="Owner name cannot be empty")
