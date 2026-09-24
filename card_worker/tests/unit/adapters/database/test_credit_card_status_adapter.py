import re

import pytest

from adapters.database.credit_card_status_adapter import DynamoDbCardStatusAdapter
from domain.models.card_status import CardStatus
from errors import CardNotFoundError


def build_adapter(client) -> DynamoDbCardStatusAdapter:
    # The table name comes from the test environment (Settings).
    return DynamoDbCardStatusAdapter(client=client)


def test_a_pending_card_reaches_the_terminal_state_and_refreshes_updated_at(
    dynamodb_client, card_store
):
    card_id = "11111111-1111-4111-8111-111111111111"
    stored = card_store.put(card_id)
    adapter = build_adapter(dynamodb_client)

    adapter.update_status(card_id, CardStatus.RECHAZADA)

    item = card_store.get(card_id)
    assert item["status"]["S"] == "RECHAZADA"
    # The updatedAt is refreshed to the current time (not the stored one).
    assert item["updatedAt"]["S"] != stored["updatedAt"]["S"]
    # The rest of the item is untouched.
    assert item["id"]["S"] == stored["id"]["S"]
    assert item["token"]["S"] == stored["token"]["S"]
    assert item["issuer"]["S"] == stored["issuer"]["S"]
    assert item["createdAt"]["S"] == stored["createdAt"]["S"]


def test_a_redelivered_event_with_the_same_terminal_state_is_a_noop(
    dynamodb_client, card_store
):
    card_id = "22222222-2222-4222-8222-222222222222"
    card_store.put(card_id, status="APROBADA")
    first = card_store.get(card_id)
    adapter = build_adapter(dynamodb_client)

    adapter.update_status(card_id, CardStatus.APROBADA)

    # Idempotency under at least once delivery: the item is not rewritten.
    assert card_store.get(card_id) == first


def test_a_terminal_card_is_updated_when_the_status_changes(
    dynamodb_client, card_store
):
    card_id = "33333333-3333-4333-8333-333333333333"
    card_store.put(card_id, status="RECHAZADA")
    adapter = build_adapter(dynamodb_client)

    adapter.update_status(card_id, CardStatus.APROBADA)

    assert card_store.get(card_id)["status"]["S"] == "APROBADA"


def test_a_missing_card_raises(dynamodb_client):
    adapter = build_adapter(dynamodb_client)

    with pytest.raises(CardNotFoundError):
        adapter.update_status("99999999-9999-4999-8999-999999999999", CardStatus.APROBADA)


def test_the_updated_at_follows_the_storage_contract(dynamodb_client, card_store):
    card_id = "44444444-4444-4444-8444-444444444444"
    card_store.put(card_id)
    adapter = build_adapter(dynamodb_client)

    adapter.update_status(card_id, CardStatus.APROBADA)

    value = card_store.get(card_id)["updatedAt"]["S"]
    # ISO yyyy-mm-ddTHH:MM:SS (no microseconds, no timezone suffix).
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value)
