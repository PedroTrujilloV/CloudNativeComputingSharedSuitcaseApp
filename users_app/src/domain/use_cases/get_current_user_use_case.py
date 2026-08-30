from datetime import datetime, timezone

from domain.models.user import User
from domain.ports.user_repository_port import UserRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from errors import InvalidTokenError


class GetCurrentUserUseCase(BaseUseCase):
    """Resolve the authenticated user from an opaque bearer token."""

    def __init__(self, user_repository: UserRepositoryPort):
        self.user_repository = user_repository

    def execute(self, *, token: str) -> User:
        user = self.user_repository.get_by_token(token)
        if user is None or user.expireAt is None:
            raise InvalidTokenError("Invalid or expired token")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if user.expireAt < now:
            raise InvalidTokenError("Invalid or expired token")

        return user
