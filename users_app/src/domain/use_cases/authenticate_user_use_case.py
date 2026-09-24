import logging

from adapters.security.password_hasher import verify_password
from adapters.security.token_generator import build_expire_at, generate_opaque_token
from domain.models.user import User, UserStatus
from domain.ports.user_repository_port import UserRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from errors import UserNotFoundError, UserNotVerifiedError

logger = logging.getLogger(__name__)


class AuthenticateUserUseCase(BaseUseCase):
    """Validate credentials and issue an opaque session token.

    The token is only issued when the user is in the VERIFICADO status:
    a POR_VERIFICAR or NO_VERIFICADO user never obtains a session token
    (RF-007), the attempt is rejected with ``UserNotVerifiedError`` and
    logged.
    """

    def __init__(self, user_repository: UserRepositoryPort, token_ttl_minutes: int = 60):
        self.user_repository = user_repository
        self.token_ttl_minutes = token_ttl_minutes

    def execute(self, *, username: str, password: str) -> User:
        user = self.user_repository.get_by_username(username)
        if user is None or not verify_password(password, user.password, user.salt):
            raise UserNotFoundError("Invalid username or password")

        if user.status is not UserStatus.VERIFICADO:
            logger.warning(
                "Token issuance rejected for user %s (id %s): status %s",
                username,
                user.id,
                user.status.value,
            )
            raise UserNotVerifiedError(
                f"User {username} is not verified (status {user.status.value})"
            )

        user.token = generate_opaque_token()
        user.expireAt = build_expire_at(self.token_ttl_minutes)
        return self.user_repository.update(user)
