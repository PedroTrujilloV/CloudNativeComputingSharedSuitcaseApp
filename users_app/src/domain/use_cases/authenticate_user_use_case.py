from adapters.security.password_hasher import verify_password
from adapters.security.token_generator import build_expire_at, generate_opaque_token
from domain.models.user import User
from domain.ports.user_repository_port import UserRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from errors import UserNotFoundError


class AuthenticateUserUseCase(BaseUseCase):
    """Validate credentials and issue an opaque session token."""

    def __init__(self, user_repository: UserRepositoryPort, token_ttl_minutes: int = 60):
        self.user_repository = user_repository
        self.token_ttl_minutes = token_ttl_minutes

    def execute(self, *, username: str, password: str) -> User:
        user = self.user_repository.get_by_username(username)
        if user is None or not verify_password(password, user.password, user.salt):
            raise UserNotFoundError("Invalid username or password")

        user.token = generate_opaque_token()
        user.expireAt = build_expire_at(self.token_ttl_minutes)
        return self.user_repository.update(user)
