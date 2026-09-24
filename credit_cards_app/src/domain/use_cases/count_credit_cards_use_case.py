"""Use case for counting the stored credit cards (GET /credit-cards/count).

The count is a utility endpoint of the API specification: it reports the
current number of stored cards without any authentication.
"""

from domain.ports.credit_card_repository_port import CreditCardRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class CountCreditCardsUseCase(BaseUseCase):
    """Returns the number of stored cards."""

    def __init__(self, credit_card_repository: CreditCardRepositoryPort):
        self.credit_card_repository = credit_card_repository

    def execute(self) -> int:
        """Return the number of stored cards."""
        return self.credit_card_repository.count()
