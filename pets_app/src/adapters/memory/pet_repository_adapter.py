from typing import Dict, List, Optional

from domain.models.pet import Pet
from domain.ports.pet_repository_port import PetRepositoryPort
from errors import PetNotFoundError


class InMemoryPetRepositoryAdapter(PetRepositoryPort):
    """In memory implementation of PetRepository."""

    memory_store: Dict[int, Pet] = {}

    def sequence(self) -> int:
        """Generate a new sequence number."""
        return len(self.memory_store) + 1

    def create(self, pet: Pet) -> Pet:
        """Create a new pet."""
        pet.id = self.sequence()
        self.memory_store[pet.id] = pet
        return pet

    def get_by_id(self, pet_id: int) -> Optional[Pet]:
        """Get pet by ID."""
        return self.memory_store.get(pet_id)

    def get_all(self) -> List[Pet]:
        """Get all pets."""
        return list(self.memory_store.values())

    def update(self, pet: Pet) -> Pet:
        """Update an existing pet."""
        if pet.id not in self.memory_store:
            raise PetNotFoundError(f"Pet with id {pet.id} not found")
        self.memory_store[pet.id] = pet
        return pet

    def delete(self, pet_id: int) -> Pet:
        """Delete a pet."""
        if pet_id not in self.memory_store:
            raise PetNotFoundError(f"Pet with id {pet_id} not found")
        pet = self.memory_store[pet_id]
        del self.memory_store[pet_id]
        return pet
