from uuid import UUID

from domain.models.offer import Offer
from domain.ports.offer_repository_port import OfferRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class ListOffersUseCase(BaseUseCase):
    """Use case for listing offers with optional AND filters."""

    def __init__(self, offer_repository: OfferRepositoryPort):
        self.offer_repository = offer_repository

    def execute(
        self,
        post_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> list[Offer]:
        """List offers, optionally filtered by post and owner."""
        return self.offer_repository.search(
            post_id=post_id,
            user_id=user_id,
        )