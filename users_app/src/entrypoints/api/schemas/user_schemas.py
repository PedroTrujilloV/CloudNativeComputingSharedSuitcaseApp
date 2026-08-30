import re

from pydantic import BaseModel, Field, field_validator, model_validator

from domain.models.user import UserStatus


class CreateUserRequest(BaseModel):
    """Request body for POST /users."""

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    email: str = Field(min_length=3)
    dni: str | None = None
    fullName: str | None = None
    phoneNumber: str | None = None

    @field_validator("username")
    @classmethod
    def username_must_be_valid(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_]+", value):
            raise ValueError("username must not contain spaces or special characters")
        return value

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("email format is invalid")
        return value


class CreateUserResponse(BaseModel):
    """Success response for POST /users."""

    id: str
    createdAt: str


class AuthUserRequest(BaseModel):
    """Request body for POST /users/auth."""

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthUserResponse(BaseModel):
    """Success response for POST /users/auth."""

    id: str
    token: str
    expireAt: str


class MeUserResponse(BaseModel):
    """Success response for GET /users/me."""

    id: str
    username: str
    email: str
    fullName: str | None = None
    dni: str | None = None
    phoneNumber: str | None = None
    status: str


class UpdateUserRequest(BaseModel):
    """Request body for PATCH /users/{id} (public, partial update)."""

    status: str | None = None
    dni: str | None = None
    fullName: str | None = None
    phoneNumber: str | None = None

    @field_validator("status")
    @classmethod
    def status_must_be_allowed(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            return UserStatus(value).value
        except ValueError as exc:
            raise ValueError("status is invalid") from exc

    @model_validator(mode="after")
    def at_least_one_updatable_field(self):
        allowed = {"status", "dni", "fullName", "phoneNumber"}
        if not (self.model_fields_set & allowed):
            raise ValueError(
                "at least one of status, dni, fullName, phoneNumber is required"
            )
        return self


class UpdateUserResponse(BaseModel):
    """Success response for PATCH /users/{id}."""

    msg: str


class CountUsersResponse(BaseModel):
    """Success response for GET /users/count."""

    count: int


class ResetUsersResponse(BaseModel):
    """Success response for POST /users/reset."""

    msg: str
