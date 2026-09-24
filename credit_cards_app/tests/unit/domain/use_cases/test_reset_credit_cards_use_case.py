from domain.ports.credit_card_repository_port import CreditCardRepositoryPort
from domain.use_cases.reset_credit_cards_use_case import ResetCreditCardsUseCase


class ResetRepository(CreditCardRepositoryPort):
    """Repository fake that records the reset call and returns a count."""

    def __init__(self, stored: int):
        self.stored = stored
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
        return self.stored

    def delete_all(self) -> int:
        self.calls += 1
        deleted = self.stored
        self.stored = 0
        return deleted


def test_the_reset_deletes_every_card_and_returns_the_count():
    use_case = ResetCreditCardsUseCase(credit_card_repository=ResetRepository(3))

    assert use_case.execute() == 3
    assert use_case.credit_card_repository.count() == 0


def test_the_reset_on_an_empty_table_returns_zero():
    use_case = ResetCreditCardsUseCase(credit_card_repository=ResetRepository(0))

    assert use_case.execute() == 0
