from abc import ABC, abstractmethod
from typing import List, Optional

from domain.models.pet import Pet


class PetRepositoryPort(ABC):
    """Pet repository interface."""

    @abstractmethod
    def create(self, pet: Pet) -> Pet:
        """Create a new pet."""
        pass

    @abstractmethod
    def get_by_id(self, pet_id: int) -> Optional[Pet]:
        """Get pet by ID."""
        pass

    @abstractmethod
    def get_all(self) -> List[Pet]:
        """Get all pets."""
        pass

    @abstractmethod
    def update(self, pet: Pet) -> Pet:
        """Update an existing pet."""
        pass

    @abstractmethod
    def delete(self, pet_id: int) -> Pet:
        """Delete a pet."""
        pass
