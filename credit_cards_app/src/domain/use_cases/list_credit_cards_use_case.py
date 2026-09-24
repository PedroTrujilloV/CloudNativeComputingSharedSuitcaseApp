"""Use case for listing the caller's credit cards (GET /credit-cards).

The listing is strictly user scoped: the repository call always carries
the caller id, so the answer only ever contains the cards the caller
owns. Cards stored by other users are unreachable through this flow.
"""

from domain.models.credit_card import CreditCard
from domain.ports.credit_card_repository_port import CreditCardRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class ListCreditCardsUseCase(BaseUseCase):
    """Returns the stored cards owned by the authenticated caller."""

    def __init__(self, credit_card_repository: CreditCardRepositoryPort):
        self.credit_card_repository = credit_card_repository

    def execute(self, user_id: str) -> list[CreditCard]:
        """Return the caller's stored cards, never the cards of other users."""
        return self.credit_card_repository.search(user_id)
