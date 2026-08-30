from uuid import UUID

from domain.models.offer import Offer
from domain.ports.offer_repository_port import OfferRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from errors import OfferNotFoundError


class GetOfferUseCase(BaseUseCase):
    """Use case for retrieving a single offer."""

    def __init__(self, offer_repository: OfferRepositoryPort):
        self.offer_repository = offer_repository

    def execute(self, offer_id: UUID) -> Offer:
        """Retrieve an offer by its id."""
        offer = self.offer_repository.get_by_id(offer_id)
        if offer is None:
            raise OfferNotFoundError("Offer not found")
        return offer