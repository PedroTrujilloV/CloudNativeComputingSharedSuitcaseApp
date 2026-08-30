from domain.ports.user_repository_port import UserRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class CountUsersUseCase(BaseUseCase):
    """Return how many users are stored."""

    def __init__(self, user_repository: UserRepositoryPort):
        self.user_repository = user_repository

    def execute(self) -> int:
        return self.user_repository.count()
