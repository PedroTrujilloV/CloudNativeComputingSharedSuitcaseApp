from adapters.memory.pet_repository_adapter import InMemoryPetRepositoryAdapter
from domain.use_cases.base_use_case import BaseUseCase
from domain.use_cases.create_pet_use_case import CreatePetUseCase
from domain.use_cases.delete_pet_use_case import DeletePetUseCase
from domain.use_cases.get_pet_use_case import GetPetUseCase
from domain.use_cases.get_pets_use_case import GetAllPetsUseCase
from domain.use_cases.update_pet_use_case import UpdatePetUseCase

repository: InMemoryPetRepositoryAdapter = InMemoryPetRepositoryAdapter()


def build_create_pet_use_case() -> BaseUseCase:
    """Get create pet use case."""
    return CreatePetUseCase(repository)


def build_get_pet_use_case() -> BaseUseCase:
    """Get pet use case."""
    return GetPetUseCase(repository)


def build_get_pets_use_case() -> BaseUseCase:
    """Get pets use case."""
    return GetAllPetsUseCase(repository)


def build_update_pet_use_case() -> BaseUseCase:
    """Update pet use case."""
    return UpdatePetUseCase(repository)


def build_delete_pet_use_case() -> BaseUseCase:
    """Get delete pet use case."""
    return DeletePetUseCase(repository)
