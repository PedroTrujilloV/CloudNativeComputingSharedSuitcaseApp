from domain.models.offer import Offer, PackageSize
from domain.ports.offer_repository_port import OfferRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from errors import InvalidOfferError


class CreateOfferUseCase(BaseUseCase):
    """Use case for creating an offer."""

    def __init__(self, offer_repository: OfferRepositoryPort):
        self.offer_repository = offer_repository

    def execute(self, offer: Offer) -> Offer:
        """Create a new offer."""
        if len(offer.description) > 140:
            raise InvalidOfferError(
                "Description cannot be longer than 140 characters"
            )
        if offer.offer.as_tuple().exponent < -2:
            raise InvalidOfferError(
                "Offer must have at most two decimal places"
            )
        if offer.offer < 0:
            raise InvalidOfferError("Offer amount must be non-negative")
        if not isinstance(offer.size, PackageSize) or offer.size not in PackageSize:
            raise InvalidOfferError("Invalid package size")
        return self.offer_repository.create(offer)
