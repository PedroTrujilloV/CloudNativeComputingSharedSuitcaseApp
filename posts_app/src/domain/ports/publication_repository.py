"""
Publication Repository Port (Interface).
Defines the contract for publication persistence operations.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from domain.models.publication import Publication


class PublicationRepository(ABC):
    """Abstract interface for publication persistence."""

    @abstractmethod
    def create(
        self,
        route_id: str,
        user_id: str,
        expire_at: datetime,
    ) -> Publication:
        """Create a new publication."""
        pass

    @abstractmethod
    def get_by_id(self, publication_id: str) -> Optional[Publication]:
        """Get publication by ID."""
        pass

    @abstractmethod
    def list(
        self,
        route_id: Optional[str] = None,
        user_id: Optional[str] = None,
        expire_status: Optional[str] = None,
    ) -> List[Publication]:
        """List publications with optional filters."""
        pass

    @abstractmethod
    def delete(self, publication_id: str) -> bool:
        """Delete publication by ID."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Count total publications."""
        pass

    @abstractmethod
    def delete_all(self) -> int:
        """Delete all publications."""
        pass
