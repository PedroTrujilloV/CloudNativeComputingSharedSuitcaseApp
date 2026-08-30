from abc import ABC, abstractmethod
from uuid import UUID

from domain.models.offer import Offer


class OfferRepositoryPort(ABC):
    @abstractmethod
    def create(self, offer: Offer) -> Offer:
        pass

    @abstractmethod
    def get_by_id(
        self,
        offer_id: UUID,
    ) -> Offer | None:
        pass

    @abstractmethod
    def search(
        self,
        post_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> list[Offer]:
        pass

    @abstractmethod
    def delete(
        self,
        offer_id: UUID,
    ) -> bool:
        pass

    @abstractmethod
    def count(self) -> int:
        pass

    @abstractmethod
    def delete_all(self) -> int:
        pass
