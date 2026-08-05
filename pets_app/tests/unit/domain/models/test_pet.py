import pytest
from pydantic import ValidationError

from domain.models.pet import Pet, PetType


def test_create_pet_with_valid_data(valid_pet_data):
    """Test creating a pet with valid data."""
    pet = Pet(**valid_pet_data)

    assert pet.id is None
    assert pet.name == valid_pet_data["name"]
    assert pet.type == valid_pet_data["type"]
    assert pet.age == valid_pet_data["age"]
    assert pet.owner_name == valid_pet_data["owner_name"]


def test_create_pet_with_id(pet_with_id):
    """Test creating a pet with an ID."""
    assert pet_with_id.id == 1
    assert pet_with_id.name == "Rex"
    assert pet_with_id.type == PetType.DOG
    assert pet_with_id.age == 5
    assert pet_with_id.owner_name == "John Doe"


def test_create_pet_with_invalid_type(valid_pet_data):
    """Test creating a pet with an invalid type."""
    with pytest.raises(ValidationError) as exc_info:
        Pet(**{**valid_pet_data, "type": "invalid_type"})  # type: ignore

    assert "type" in str(exc_info.value)
    assert "Input should be" in str(exc_info.value)


def test_create_pet_with_negative_age(valid_pet_data):
    """Test creating a pet with a negative age."""
    with pytest.raises(ValidationError) as exc_info:
        Pet(**{**valid_pet_data, "age": -1})

    assert "age" in str(exc_info.value)
    assert "Input should be greater than 0" in str(exc_info.value)


def test_create_pet_with_empty_name(valid_pet_data):
    """Test creating a pet with an empty name."""
    with pytest.raises(ValidationError) as exc_info:
        Pet(**{**valid_pet_data, "name": ""})

    assert "name" in str(exc_info.value)
    assert "String should have at least 1 character" in str(exc_info.value)


def test_create_pet_with_empty_owner_name(valid_pet_data):
    """Test creating a pet with an empty owner name."""
    with pytest.raises(ValidationError) as exc_info:
        Pet(**{**valid_pet_data, "owner_name": ""})

    assert "owner_name" in str(exc_info.value)
    assert "String should have at least 1 character" in str(exc_info.value)


def test_create_pet_with_none_values():
    """Test creating a pet with None values for required fields."""
    with pytest.raises(ValidationError) as exc_info:
        Pet(
            name=None,  # type: ignore
            type=None,  # type: ignore
            age=None,  # type: ignore
            owner_name=None,  # type: ignore
        )

    assert "name" in str(exc_info.value)
    assert "type" in str(exc_info.value)
    assert "age" in str(exc_info.value)
    assert "owner_name" in str(exc_info.value)


def test_create_pet_with_extra_fields(valid_pet_data):
    """Test creating a pet with extra fields."""
    pet = Pet(**valid_pet_data, extra_field="extra")  # type: ignore

    assert not hasattr(pet, "extra_field")


def test_pet_type_enum_values():
    """Test all possible pet type enum values."""
    assert PetType.DOG == "dog"
    assert PetType.CAT == "cat"
    assert PetType.BIRD == "bird"
    assert PetType.OTHER == "other"


def test_pet_model_equality(pet_with_id):
    """Test pet model equality."""
    pet2 = Pet(id=1, name="Rex", type=PetType.DOG, age=5, owner_name="John Doe")

    assert pet_with_id == pet2


def test_pet_model_inequality(pet_with_id):
    """Test pet model inequality."""
    pet2 = Pet(id=2, name="Rex", type=PetType.DOG, age=5, owner_name="John Doe")

    assert pet_with_id != pet2


def test_pet_model_dict_conversion(pet_with_id):
    """Test pet model conversion to dictionary."""
    pet_dict = pet_with_id.model_dump()
    assert pet_dict == {
        "id": 1,
        "name": "Rex",
        "type": "dog",
        "age": 5,
        "owner_name": "John Doe",
    }


def test_pet_model_json_conversion(pet_with_id):
    """Test pet model conversion to JSON."""
    pet_json = pet_with_id.model_dump_json()
    assert (
        pet_json == '{"id":1,"name":"Rex","type":"dog","age":5,"owner_name":"John Doe"}'
    )
