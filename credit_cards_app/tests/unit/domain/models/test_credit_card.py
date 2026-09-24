from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from domain.models.credit_card import (
    ISO_UTC_FORMAT,
    CardIssuer,
    CardStatus,
    CreditCard,
    format_iso_utc,
    parse_iso_utc,
)


def _valid_kwargs(**overrides) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    data = {
        "id": str(uuid4()),
        "token": "a" * 256,
        "userId": str(uuid4()),
        "lastFourDigits": "4242",
        "ruv": "ruv-0001",
        "issuer": CardIssuer.VISA,
        "status": CardStatus.POR_VERIFICAR,
        "createdAt": now - timedelta(hours=1),
        "updatedAt": now,
    }
    data.update(overrides)
    return data


class TestCardIssuer:
    def test_exact_allowed_values(self):
        assert {member.value for member in CardIssuer} == {
            "VISA",
            "MASTERCARD",
            "AMERICAN EXPRESS",
            "DISCOVER",
            "DINERS CLUB",
            "UNKNOWN",
        }


class TestCardStatus:
    def test_exact_allowed_values(self):
        assert {member.value for member in CardStatus} == {
            "POR_VERIFICAR",
            "RECHAZADA",
            "APROBADA",
        }

    def test_no_verificada_value(self):
        # The entity specification does not define VERIFICADA; the model
        # must reject it even if a requirement draft mentions it.
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(status="VERIFICADA"))


class TestCreditCard:
    def test_valid_card_keeps_all_documented_fields(self):
        card = CreditCard(**_valid_kwargs())
        assert card.id
        assert card.token
        assert card.userId
        assert card.lastFourDigits == "4242"
        assert card.ruv
        assert card.issuer == CardIssuer.VISA
        assert card.status == CardStatus.POR_VERIFICAR
        assert card.createdAt.tzinfo == timezone.utc
        assert card.updatedAt.tzinfo == timezone.utc

    def test_id_must_be_a_valid_uuid(self):
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(id="not-a-uuid"))

    def test_token_is_bounded_to_256_characters(self):
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(token="a" * 257))

    def test_token_requires_a_value(self):
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(token=""))

    def test_last_four_digits_require_exactly_four_digits(self):
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(lastFourDigits="424"))
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(lastFourDigits="42424"))
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(lastFourDigits="42a2"))

    def test_empty_owner_and_ruv_are_rejected(self):
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(userId=""))
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(ruv=""))

    def test_issuer_must_be_a_documented_value(self):
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(issuer="JCB"))

    def test_status_must_be_a_documented_value(self):
        with pytest.raises(ValidationError):
            CreditCard(**_valid_kwargs(status="APPROVED"))

    def test_naive_dates_are_normalized_to_utc(self):
        created = datetime(2026, 9, 23, 12, 0, 0)
        card = CreditCard(**_valid_kwargs(createdAt=created, updatedAt=created))
        assert card.createdAt == created.replace(tzinfo=timezone.utc)
        assert card.updatedAt == created.replace(tzinfo=timezone.utc)

    def test_non_utc_dates_are_converted_to_utc(self):
        offset = timezone(timedelta(hours=5))
        created = datetime(2026, 9, 23, 12, 0, 0, tzinfo=offset)
        card = CreditCard(**_valid_kwargs(createdAt=created, updatedAt=created))
        assert card.createdAt == datetime(2026, 9, 23, 7, 0, 0, tzinfo=timezone.utc)
        assert card.updatedAt == datetime(2026, 9, 23, 7, 0, 0, tzinfo=timezone.utc)

    def test_enum_members_are_accepted_by_value(self):
        card = CreditCard(**_valid_kwargs(issuer="DISCOVER", status="RECHAZADA"))
        assert card.issuer == CardIssuer.DISCOVER
        assert card.status == CardStatus.RECHAZADA


class TestIsoUtcContract:
    def test_format_uses_the_documented_pattern(self):
        value = datetime(2026, 9, 23, 12, 34, 56, tzinfo=timezone.utc)
        assert format_iso_utc(value) == "2026-09-23T12:34:56"

    def test_format_strips_microseconds_and_forces_utc(self):
        value = datetime(
            2026, 9, 23, 12, 34, 56, 999999, tzinfo=timezone(timedelta(hours=2))
        )
        assert format_iso_utc(value) == "2026-09-23T10:34:56"

    def test_parse_returns_a_utc_datetime(self):
        value = parse_iso_utc("2026-09-23T12:34:56")
        assert value == datetime(2026, 9, 23, 12, 34, 56, tzinfo=timezone.utc)

    def test_roundtrip_keeps_second_precision(self):
        value = datetime(2026, 9, 23, 12, 34, 56, tzinfo=timezone.utc)
        assert parse_iso_utc(format_iso_utc(value)) == value

    def test_format_constant_matches_entity_contract(self):
        assert ISO_UTC_FORMAT == "%Y-%m-%dT%H:%M:%S"
