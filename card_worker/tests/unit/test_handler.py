import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from domain.models.card_verification_event import CardVerificationEvent, EVENT_TYPE
from errors import CardVerificationEventError
import handler

# Date contract of the entity: ISO yyyy-mm-ddTHH:MM:SS, UTC 0.
ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%S"


def valid_body() -> dict:
    # Dates are computed at test time (no fixed dates).
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "eventType": EVENT_TYPE,
        "cardId": str(uuid4()),
        "ruv": str(uuid4()),
        "userId": str(uuid4()),
        "lastFourDigits": "4242",
        "issuer": "VISA",
        "status": "POR_VERIFICAR",
        "createdAt": now.strftime(ISO_UTC_FORMAT),
        "ownerEmail": "owner@example.com",
    }


def sqs_event(body, receive_count=None) -> dict:
    record = {"body": body, "messageId": "m-1"}
    if receive_count is not None:
        record["attributes"] = {
            "ApproximateReceiveCount": str(receive_count),
            "SentTimestamp": "1700000000000",
        }
    return {"Records": [record]}


class RecordingUseCase:
    """Stand in for the use case: records the execute calls."""

    def __init__(self):
        self.calls = []

    def execute(self, event: CardVerificationEvent, receive_count: int = 1) -> None:
        self.calls.append((event.cardId, event.ruv, receive_count))


def test_a_valid_record_is_parsed_and_handed_to_the_use_case(monkeypatch):
    body = valid_body()
    use_case = RecordingUseCase()
    monkeypatch.setattr(handler, "build_verify_card_status_use_case", lambda: use_case)

    handler.handler(sqs_event(json.dumps(body)), None)

    assert use_case.calls == [(body["cardId"], body["ruv"], 1)]


def test_the_receive_count_of_the_record_is_forwarded(monkeypatch):
    body = valid_body()
    use_case = RecordingUseCase()
    monkeypatch.setattr(handler, "build_verify_card_status_use_case", lambda: use_case)

    handler.handler(sqs_event(json.dumps(body), receive_count=4), None)

    assert use_case.calls == [(body["cardId"], body["ruv"], 4)]


def test_every_record_of_the_batch_is_processed(monkeypatch):
    first = valid_body()
    second = valid_body()
    use_case = RecordingUseCase()
    monkeypatch.setattr(handler, "build_verify_card_status_use_case", lambda: use_case)

    handler.handler(
        {
            "Records": [
                {"body": json.dumps(first), "messageId": "m-1"},
                {"body": json.dumps(second), "messageId": "m-2"},
            ]
        },
        None,
    )

    assert use_case.calls == [
        (first["cardId"], first["ruv"], 1),
        (second["cardId"], second["ruv"], 1),
    ]


def test_an_empty_batch_is_a_noop(monkeypatch):
    use_case = RecordingUseCase()
    monkeypatch.setattr(handler, "build_verify_card_status_use_case", lambda: use_case)

    handler.handler({"Records": []}, None)

    assert use_case.calls == []


def test_a_malformed_json_body_raises():
    with pytest.raises(CardVerificationEventError):
        handler.parse_event("not a json body")


def test_a_non_object_json_body_raises():
    with pytest.raises(CardVerificationEventError):
        handler.parse_event("[1, 2, 3]")


def test_a_body_missing_a_required_field_raises():
    body = valid_body()
    del body["ruv"]
    with pytest.raises(CardVerificationEventError):
        handler.parse_event(json.dumps(body))


def test_a_body_with_an_unknown_event_type_raises():
    body = valid_body()
    body["eventType"] = "SOMETHING_ELSE"
    with pytest.raises(CardVerificationEventError):
        handler.parse_event(json.dumps(body))


def test_a_body_with_an_invalid_card_id_raises():
    body = valid_body()
    body["cardId"] = "not-a-uuid"
    with pytest.raises(CardVerificationEventError):
        handler.parse_event(json.dumps(body))


def test_an_event_without_an_owner_email_is_accepted():
    # Events published before the ownerEmail wiring may omit the field.
    body = valid_body()
    del body["ownerEmail"]
    parsed = handler.parse_event(json.dumps(body))
    assert parsed.ownerEmail == ""


def test_the_receive_count_defaults_to_one_without_attributes():
    assert handler.receive_count_of({"body": "{}"}) == 1
    assert handler.receive_count_of({}) == 1


def test_the_receive_count_comes_from_the_sqs_attributes():
    record = {
        "attributes": {
            "ApproximateReceiveCount": "3",
            "SentTimestamp": "1700000000000",
        }
    }
    assert handler.receive_count_of(record) == 3


def test_an_unparseable_receive_count_falls_back_to_one():
    record = {"attributes": {"ApproximateReceiveCount": "not-a-number"}}
    assert handler.receive_count_of(record) == 1


def test_parse_event_returns_the_domain_model():
    body = valid_body()
    parsed = handler.parse_event(json.dumps(body))
    assert isinstance(parsed, CardVerificationEvent)
    assert parsed.ruv == body["ruv"]
    assert parsed.lastFourDigits == "4242"
    assert parsed.ownerEmail == body["ownerEmail"]
