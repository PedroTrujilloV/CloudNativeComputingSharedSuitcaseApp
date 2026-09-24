import pytest

from config import Settings
from domain.models.card_verification_event import CardVerificationEvent, EVENT_TYPE


def test_the_event_model_accepts_a_valid_payload():
    event = CardVerificationEvent(
        eventType=EVENT_TYPE,
        cardId="11111111-1111-4111-8111-111111111111",
        ruv="ruv-1",
        userId="user-1",
        lastFourDigits="4242",
        issuer="VISA",
        status="POR_VERIFICAR",
        createdAt="2026-01-01T00:00:00",
    )
    assert event.cardId == "11111111-1111-4111-8111-111111111111"
    assert event.ruv == "ruv-1"


def test_an_invalid_event_type_is_rejected():
    with pytest.raises(ValueError):
        CardVerificationEvent(
            eventType="OTHER",
            cardId="11111111-1111-4111-8111-111111111111",
            ruv="ruv-1",
            userId="user-1",
            lastFourDigits="4242",
            issuer="VISA",
            status="POR_VERIFICAR",
            createdAt="2026-01-01T00:00:00",
        )


def test_an_invalid_card_id_is_rejected():
    with pytest.raises(ValueError):
        CardVerificationEvent(
            eventType=EVENT_TYPE,
            cardId="not-a-uuid",
            ruv="ruv-1",
            userId="user-1",
            lastFourDigits="4242",
            issuer="VISA",
            status="POR_VERIFICAR",
            createdAt="2026-01-01T00:00:00",
        )


def test_a_short_last_four_digits_is_rejected():
    with pytest.raises(ValueError):
        CardVerificationEvent(
            eventType=EVENT_TYPE,
            cardId="11111111-1111-4111-8111-111111111111",
            ruv="ruv-1",
            userId="user-1",
            lastFourDigits="424",
            issuer="VISA",
            status="POR_VERIFICAR",
            createdAt="2026-01-01T00:00:00",
        )


def test_a_missing_field_is_rejected():
    with pytest.raises(ValueError):
        CardVerificationEvent(
            eventType=EVENT_TYPE,
            cardId="11111111-1111-4111-8111-111111111111",
            userId="user-1",
            lastFourDigits="4242",
            issuer="VISA",
            status="POR_VERIFICAR",
            createdAt="2026-01-01T00:00:00",
        )
