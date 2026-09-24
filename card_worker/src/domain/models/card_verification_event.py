from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Event type published by the credit cards application right after it
# stores the card as POR_VERIFICAR.
EVENT_TYPE = "CARD_VERIFICATION_REQUESTED"


class CardVerificationEvent(BaseModel):
    """Verification event carried by the SQS queue.

    The payload is the one published by the credit cards application; the
    worker only needs the card id and the RUV to complete the flow, but it
    validates the whole contract so a record that does not match the
    publisher is rejected (and re delivered by the queue until the dead
    letter queue) instead of being silently dropped.
    """

    eventType: str = Field(min_length=1)
    cardId: str = Field(min_length=1)
    ruv: str = Field(min_length=1)
    userId: str = Field(min_length=1)
    lastFourDigits: str = Field(min_length=4, max_length=4)
    issuer: str = Field(min_length=1)
    status: str = Field(min_length=1)
    createdAt: str = Field(min_length=1)
    # The owner email, resolved by the credit cards application through the
    # users application API (GET /users/me) at creation time and carried in
    # the event so the worker can address the email notification. Events in
    # flight before that wiring may omit it, so it defaults to empty.
    ownerEmail: str = ""

    @field_validator("eventType")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        if value != EVENT_TYPE:
            raise ValueError(f"eventType must be {EVENT_TYPE}")
        return value

    @field_validator("cardId")
    @classmethod
    def validate_card_id(cls, value: str) -> str:
        try:
            UUID(value)
        except ValueError as exc:
            raise ValueError("cardId must be a valid UUID") from exc
        return value
