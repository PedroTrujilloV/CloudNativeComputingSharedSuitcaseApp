from uuid import UUID

from domain.ports.offer_repository_port import OfferRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from errors import OfferNotFoundError


class DeleteOfferUseCase(BaseUseCase):
    """Use case for deleting a single offer."""

    def __init__(self, offer_repository: OfferRepositoryPort):
        self.offer_repository = offer_repository

    def execute(self, offer_id: UUID) -> None:
        """Delete an offer by its id."""
        deleted = self.offer_repository.delete(offer_id)
        if not deleted:
            raise OfferNotFoundError("Offer not found")