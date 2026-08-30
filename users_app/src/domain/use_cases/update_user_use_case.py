from domain.models.user import User, UserStatus
from domain.ports.user_repository_port import UserRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from errors import UserNotFoundError


class UpdateUserUseCase(BaseUseCase):
    """Update mutable public profile fields for an existing user."""

    def __init__(self, user_repository: UserRepositoryPort):
        self.user_repository = user_repository

    def execute(
        self,
        *,
        user_id: str,
        fields_set: set[str],
        status: str | None = None,
        dni: str | None = None,
        fullName: str | None = None,
        phoneNumber: str | None = None,
    ) -> User:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User with id {user_id} not found")

        if "status" in fields_set:
            user.status = UserStatus(status)
        if "dni" in fields_set:
            user.dni = dni
        if "fullName" in fields_set:
            user.fullName = fullName
        if "phoneNumber" in fields_set:
            user.phoneNumber = phoneNumber

        return self.user_repository.update(user)
