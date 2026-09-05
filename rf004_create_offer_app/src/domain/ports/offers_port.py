"""Port for the Offers service (offer persistence)."""

from abc import ABC, abstractmethod


class OffersPort(ABC):
    """Abstraction over the Offers service's public API."""

    @abstractmethod
    def create_offer(
        self,
        postId: str,
        userId: str,
        description: str,
        size: str,
        fragile: bool,
        offer: float,
    ) -> dict:
        """Create an offer via the Offers service.

        Raises:
            OfferCreationFailedError: the offer could not be created (412/400).
            OffersServiceUnavailableError: the service is unreachable or
                fails (network error / 5xx).
        """

    @abstractmethod
    def delete_offer(self, offer_id: str) -> None:
        """Delete an offer via the Offers service (compensating action).

        Raises:
            OffersServiceUnavailableError: the service is unreachable or
                fails (network error / 5xx).
        """


class FakeOffers:
    """In-memory fake for the Offers service used in tests."""

    def __init__(self, offer_result: dict | None = None):
        self.offer_result = offer_result or {
            "id": "offer-1",
            "userId": "user-1",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        self.create_calls: list[dict] = []
        self.delete_calls: list[str] = []

    def create_offer(
        self,
        postId: str,
        userId: str,
        description: str,
        size: str,
        fragile: bool,
        offer: float,
    ) -> dict:
        self.create_calls.append({
            "postId": postId,
            "userId": userId,
            "description": description,
            "size": size,
            "fragile": fragile,
            "offer": offer,
        })
        return self.offer_result

    def delete_offer(self, offer_id: str) -> None:
        self.delete_calls.append(offer_id)
