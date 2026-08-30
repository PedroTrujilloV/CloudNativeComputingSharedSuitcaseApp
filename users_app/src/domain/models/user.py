from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class UserStatus(str, Enum):
    """Allowed user status values from the information view."""

    POR_VERIFICAR = "POR_VERIFICAR"
    NO_VERIFICADO = "NO_VERIFICADO"
    VERIFICADO = "VERIFICADO"


class User(BaseModel):
    """Usuario domain model."""

    id: str | None = None
    username: str = Field(min_length=1)
    email: str = Field(min_length=3)

    phoneNumber: str | None = None
    dni: str | None = None
    fullName: str | None = None
    password: str = Field(min_length=1, description="Hashed password")
    salt: str = Field(min_length=1)
    token: str | None = None
    status: UserStatus = UserStatus.POR_VERIFICAR
    expireAt: datetime | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
