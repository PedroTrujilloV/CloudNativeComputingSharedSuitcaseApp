from domain.ports.offer_repository_port import OfferRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class CountOffersUseCase(BaseUseCase):
    """Use case for counting stored offers."""

    def __init__(self, offer_repository: OfferRepositoryPort):
        self.offer_repository = offer_repository

    def execute(self) -> int:
        """Return the number of stored offers."""
        return self.offer_repository.count()