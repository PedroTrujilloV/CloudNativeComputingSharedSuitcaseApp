from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CardIssuer(str, Enum):
    """Allowed issuer values from the information view."""

    VISA = "VISA"
    MASTERCARD = "MASTERCARD"
    AMERICAN_EXPRESS = "AMERICAN EXPRESS"
    DISCOVER = "DISCOVER"
    DINERS_CLUB = "DINERS CLUB"
    UNKNOWN = "UNKNOWN"


class CardStatus(str, Enum):
    """Allowed card status values from the information view.

    The entity specification defines exactly these three values; the
    acceptance criteria of RF-006 that mention a card stored as
    VERIFICADA are covered by this enum as POR_VERIFICAR until the
    asynchronous worker reaches a terminal state.
    """

    POR_VERIFICAR = "POR_VERIFICAR"
    RECHAZADA = "RECHAZADA"
    APROBADA = "APROBADA"


# Date contract of the entity: ISO yyyy-mm-ddTHH:MM:SS in UTC 0.
ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%S"


def format_iso_utc(value: datetime) -> str:
    """Render a datetime in the entity contract format (UTC, second precision)."""
    return value.astimezone(timezone.utc).strftime(ISO_UTC_FORMAT)


def parse_iso_utc(value: str) -> datetime:
    """Parse an ISO yyyy-mm-ddTHH:MM:SS string as a UTC datetime."""
    return datetime.strptime(value, ISO_UTC_FORMAT).replace(tzinfo=timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC 0.

    A naive datetime is assumed to be already in UTC; an aware datetime is
    converted, so every stored date honors the entity contract.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class CreditCard(BaseModel):
    """CreditCard domain model, exclusive to the credit cards application.

    Only the documented fields exist here: the raw card number and the CVV
    are consumed by the tokenization call and are never stored.
    """

    id: str = Field(min_length=1, description="Card identifier in UUID format")
    token: str = Field(
        min_length=1,
        max_length=256,
        description="Payment platform token (256 characters)",
    )
    userId: str = Field(min_length=1, description="Owner user identifier")
    lastFourDigits: str = Field(
        min_length=4, max_length=4, description="Last four digits of the card"
    )
    ruv: str = Field(min_length=1, description="Unique verification record")
    issuer: CardIssuer
    status: CardStatus
    createdAt: datetime
    updatedAt: datetime

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        try:
            UUID(value)
        except ValueError as exc:
            raise ValueError("id must be a valid UUID") from exc
        return value

    @field_validator("lastFourDigits")
    @classmethod
    def validate_last_four_digits(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("lastFourDigits must contain only digits")
        return value

    @field_validator("createdAt", "updatedAt")
    @classmethod
    def validate_dates_utc(cls, value: datetime) -> datetime:
        return _as_utc(value)
