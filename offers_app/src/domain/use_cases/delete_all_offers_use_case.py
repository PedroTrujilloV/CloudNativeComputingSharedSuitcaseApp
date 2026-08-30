from domain.ports.offer_repository_port import OfferRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class DeleteAllOffersUseCase(BaseUseCase):
    """Use case for deleting all offers."""

    def __init__(self, offer_repository: OfferRepositoryPort):
        self.offer_repository = offer_repository

    def execute(self) -> None:
        """Delete all offers."""
        self.offer_repository.delete_all()
