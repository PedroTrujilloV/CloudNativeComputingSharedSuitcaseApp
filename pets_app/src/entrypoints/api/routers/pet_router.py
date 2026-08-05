from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from assembly import (
    build_create_pet_use_case,
    build_delete_pet_use_case,
    build_get_pet_use_case,
    build_get_pets_use_case,
    build_update_pet_use_case,
)
from domain.models.pet import Pet
from domain.use_cases.base_use_case import BaseUseCase
from errors import PetNotFoundError

router = APIRouter(prefix="/pets")


@router.get("/ping", response_class=PlainTextResponse)
def health_check():
    """Healthcheck endpoint."""
    return "pong"


@router.post("/", response_model=Pet)
def create_pet(pet: Pet, use_case: BaseUseCase = Depends(build_create_pet_use_case)):
    """Create a new pet."""
    return use_case.execute(pet)


@router.get("/{pet_id}", response_model=Pet)
def get_pet(pet_id: int, use_case: BaseUseCase = Depends(build_get_pet_use_case)):
    """Get a pet by ID."""
    pet = use_case.execute(pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet


@router.get("/", response_model=List[Pet])
def get_pets(use_case: BaseUseCase = Depends(build_get_pets_use_case)):
    """Get all pets."""
    return use_case.execute()


@router.put("/{pet_id}", response_model=Pet)
def update_pet(
    pet_id: int, pet: Pet, use_case: BaseUseCase = Depends(build_update_pet_use_case)
):
    """Update pet."""
    try:
        pet.id = pet_id
        return use_case.execute(pet)
    except PetNotFoundError as err:
        return JSONResponse({"error": str(err)}, status_code=404)


@router.delete("/{pet_id}", response_model=Pet)
def delete_pet(pet_id: int, use_case: BaseUseCase = Depends(build_delete_pet_use_case)):
    """Delete pet."""
    try:
        return use_case.execute(pet_id)
    except PetNotFoundError as err:
        return JSONResponse({"error": str(err)}, status_code=404)
