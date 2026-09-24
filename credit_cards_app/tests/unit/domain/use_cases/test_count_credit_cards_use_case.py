from domain.ports.credit_card_repository_port import CreditCardRepositoryPort
from domain.use_cases.count_credit_cards_use_case import CountCreditCardsUseCase


class CountRepository(CreditCardRepositoryPort):
    """Repository fake with a fixed count."""

    def __init__(self, total: int):
        self.total = total
        self.calls = 0

    def create(self, card):
        raise NotImplementedError

    def get_by_id(self, card_id: str):
        raise NotImplementedError

    def search(self, user_id: str | None = None):
        raise NotImplementedError

    def update_status(self, card_id, status):
        raise NotImplementedError

    def count(self) -> int:
        self.calls += 1
        return self.total

    def delete_all(self) -> int:
        raise NotImplementedError


def test_the_count_comes_from_the_repository():
    use_case = CountCreditCardsUseCase(credit_card_repository=CountRepository(7))

    assert use_case.execute() == 7
    assert use_case.credit_card_repository.calls == 1


def test_the_count_is_zero_on_an_empty_table():
    use_case = CountCreditCardsUseCase(credit_card_repository=CountRepository(0))

    assert use_case.execute() == 0
