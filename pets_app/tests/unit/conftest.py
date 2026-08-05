import pytest

from domain.models.pet import Pet, PetType


@pytest.fixture
def valid_pet_data():
    """Fixture providing valid pet data."""
    return {"name": "Rex", "type": PetType.DOG, "age": 5, "owner_name": "John Doe"}


@pytest.fixture
def pet_with_id():
    """Fixture providing a pet with ID."""
    return Pet(id=1, name="Rex", type=PetType.DOG, age=5, owner_name="John Doe")
