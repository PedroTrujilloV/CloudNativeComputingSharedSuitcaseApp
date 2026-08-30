from domain.ports.user_repository_port import UserRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class ResetUsersUseCase(BaseUseCase):
    """Delete all persisted users."""

    def __init__(self, user_repository: UserRepositoryPort):
        self.user_repository = user_repository

    def execute(self) -> None:
        self.user_repository.delete_all()
