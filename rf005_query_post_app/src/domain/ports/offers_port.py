"""Offers port (contract) for the RF-005 orchestrator."""

from abc import ABC, abstractmethod


class OffersPort(ABC):
    """Abstraction over the Offers service public API."""

    @abstractmethod
    def get_offers(self, post_id: str) -> list[dict]:
        """Fetch all offers for a given post id via the Offers service.

        Returns an empty list when no offers exist (not an error).

        Raises:
            OffersServiceUnavailableError: when the service is unreachable
                or errors (network error / 5xx).
        """
