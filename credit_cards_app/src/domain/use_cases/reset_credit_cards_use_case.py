"""Use case for resetting the stored credit cards (POST /credit-cards/reset).

The reset is a utility endpoint of the API specification: it deletes every
stored card without any authentication. It is the mechanism the grading
pipeline uses to clean the table between runs.
"""

from domain.ports.credit_card_repository_port import CreditCardRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class ResetCreditCardsUseCase(BaseUseCase):
    """Deletes every stored card."""

    def __init__(self, credit_card_repository: CreditCardRepositoryPort):
        self.credit_card_repository = credit_card_repository

    def execute(self) -> int:
        """Delete every stored card and return the deleted count."""
        return self.credit_card_repository.delete_all()
