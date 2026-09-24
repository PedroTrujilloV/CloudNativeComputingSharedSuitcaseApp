from datetime import timedelta, timezone

from adapters.database.credit_card_repository_adapter import (
    DynamoDbCreditCardRepositoryAdapter,
)
from domain.models.credit_card import CardStatus


def _adapter(dynamodb_resource, table_name: str = "test_credit_cards"):
    return DynamoDbCreditCardRepositoryAdapter(
        table=dynamodb_resource.Table(table_name), table_name=table_name
    )


class TestDynamoDbCreditCardRepositoryAdapter:
    def test_create_persists_and_returns_card(self, dynamodb_resource, card_factory):
        adapter = _adapter(dynamodb_resource)
        card = card_factory()

        stored = adapter.create(card)

        assert stored.id == card.id
        assert adapter.get_by_id(card.id) is not None

    def test_roundtrip_preserves_every_documented_field(
        self, dynamodb_resource, card_factory
    ):
        adapter = _adapter(dynamodb_resource)
        card = card_factory()

        adapter.create(card)
        loaded = adapter.get_by_id(card.id)

        assert loaded == card
        assert loaded.id == card.id
        assert loaded.token == card.token
        assert loaded.userId == card.userId
        assert loaded.lastFourDigits == card.lastFourDigits
        assert loaded.ruv == card.ruv
        assert loaded.issuer == card.issuer
        assert loaded.status == card.status
        assert loaded.createdAt == card.createdAt
        assert loaded.updatedAt == card.updatedAt

    def test_stored_item_uses_the_iso_utc_contract(
        self, dynamodb_resource, card_factory
    ):
        adapter = _adapter(dynamodb_resource)
        card = card_factory()

        adapter.create(card)
        item = adapter.table.get_item(Key={"id": card.id})["Item"]

        assert len(item["createdAt"]) == 19
        assert item["createdAt"].endswith(card.createdAt.strftime("%H:%M:%S"))
        assert len(item["updatedAt"]) == 19
        assert "T" in item["createdAt"]

    def test_get_by_id_returns_none_when_missing(self, dynamodb_resource):
        adapter = _adapter(dynamodb_resource)
        assert adapter.get_by_id("missing-id") is None

    def test_search_filters_by_owner_through_the_gsi(
        self, dynamodb_resource, card_factory
    ):
        adapter = _adapter(dynamodb_resource)
        owner_a = card_factory()
        owner_a_second = card_factory(userId=owner_a.userId)
        owner_b = card_factory()

        for card in (owner_a, owner_a_second, owner_b):
            adapter.create(card)

        results = adapter.search(user_id=owner_a.userId)
        assert {card.id for card in results} == {owner_a.id, owner_a_second.id}

    def test_search_without_owner_returns_every_card(
        self, dynamodb_resource, card_factory
    ):
        adapter = _adapter(dynamodb_resource)
        first = card_factory()
        second = card_factory()

        adapter.create(first)
        adapter.create(second)

        assert {card.id for card in adapter.search()} == {first.id, second.id}

    def test_update_status_changes_status_and_refreshes_updated_at(
        self, dynamodb_resource, card_factory
    ):
        adapter = _adapter(dynamodb_resource)
        card = card_factory()

        adapter.create(card)
        updated = adapter.update_status(card.id, CardStatus.APROBADA)

        assert updated is not None
        assert updated.status == CardStatus.APROBADA
        assert updated.id == card.id
        assert updated.updatedAt >= card.createdAt + timedelta(seconds=1)
        reloaded = adapter.get_by_id(card.id)
        assert reloaded.status == CardStatus.APROBADA
        assert reloaded.updatedAt == updated.updatedAt

    def test_update_status_to_rechazada(self, dynamodb_resource, card_factory):
        adapter = _adapter(dynamodb_resource)
        card = card_factory()

        adapter.create(card)
        updated = adapter.update_status(card.id, CardStatus.RECHAZADA)

        assert updated is not None
        assert updated.status == CardStatus.RECHAZADA

    def test_update_status_of_missing_card_returns_none(self, dynamodb_resource):
        adapter = _adapter(dynamodb_resource)
        assert (
            adapter.update_status("missing-id", CardStatus.APROBADA) is None
        )

    def test_update_status_is_idempotent_for_redelivered_events(
        self, dynamodb_resource, card_factory
    ):
        adapter = _adapter(dynamodb_resource)
        card = card_factory()

        adapter.create(card)
        first = adapter.update_status(card.id, CardStatus.APROBADA)
        second = adapter.update_status(card.id, CardStatus.APROBADA)

        assert second.status == CardStatus.APROBADA
        assert first.id == second.id

    def test_count_returns_the_number_of_stored_cards(
        self, dynamodb_resource, card_factory
    ):
        adapter = _adapter(dynamodb_resource)
        assert adapter.count() == 0

        for _ in range(3):
            adapter.create(card_factory())

        assert adapter.count() == 3

    def test_delete_all_removes_every_card(self, dynamodb_resource, card_factory):
        adapter = _adapter(dynamodb_resource)
        cards = [card_factory() for _ in range(3)]

        for card in cards:
            adapter.create(card)

        deleted = adapter.delete_all()

        assert deleted == 3
        assert adapter.count() == 0
        for card in cards:
            assert adapter.get_by_id(card.id) is None

    def test_delete_all_on_empty_table_returns_zero(self, dynamodb_resource):
        adapter = _adapter(dynamodb_resource)
        assert adapter.delete_all() == 0
