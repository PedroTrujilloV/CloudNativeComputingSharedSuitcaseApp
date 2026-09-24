from uuid import uuid4

from domain.ports.credit_card_repository_port import CreditCardRepositoryPort
from domain.use_cases.list_credit_cards_use_case import ListCreditCardsUseCase


class RecordingRepository(CreditCardRepositoryPort):
    """Repository fake that records every search it receives."""

    def __init__(self, cards):
        self.cards = cards
        self.search_calls: list[str | None] = []

    def create(self, card):
        raise NotImplementedError

    def get_by_id(self, card_id: str):
        raise NotImplementedError

    def search(self, user_id: str | None = None):
        self.search_calls.append(user_id)
        if user_id is None:
            return list(self.cards)
        return [card for card in self.cards if card.userId == user_id]

    def update_status(self, card_id, status):
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def delete_all(self) -> int:
        raise NotImplementedError


def test_the_listing_returns_only_the_cards_of_the_caller(card_factory):
    user_1 = str(uuid4())
    user_2 = str(uuid4())
    card_one = card_factory(userId=user_1)
    card_two = card_factory(userId=user_2)
    card_three = card_factory(userId=user_1)
    cards = [card_one, card_two, card_three]
    use_case = ListCreditCardsUseCase(
        credit_card_repository=RecordingRepository(cards)
    )

    result = use_case.execute(user_1)

    assert [card.id for card in result] == [
        card_one.id,
        card_three.id,
    ]
    assert all(card.userId == user_1 for card in result)


def test_the_repository_call_always_carries_the_caller_id(card_factory):
    use_case = ListCreditCardsUseCase(
        credit_card_repository=RecordingRepository([])
    )

    use_case.execute("user-2")

    # The filter is the caller id itself, never an unfiltered scan that
    # would expose the cards of other users.
    assert use_case.credit_card_repository.search_calls == ["user-2"]


def test_the_listing_returns_an_empty_list_when_the_caller_owns_no_cards(
    card_factory,
):
    cards = [card_factory(userId="user-1")]
    use_case = ListCreditCardsUseCase(
        credit_card_repository=RecordingRepository(cards)
    )

    assert use_case.execute("user-2") == []
