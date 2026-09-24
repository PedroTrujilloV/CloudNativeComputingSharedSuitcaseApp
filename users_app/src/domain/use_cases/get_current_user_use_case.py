import logging
from datetime import datetime, timezone

from domain.models.user import User, UserStatus
from domain.ports.user_repository_port import UserRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from errors import InvalidTokenError

logger = logging.getLogger(__name__)


class GetCurrentUserUseCase(BaseUseCase):
    """Resolve the authenticated user from an opaque bearer token.

    The token is only accepted when the user it belongs to is in the
    VERIFICADO status (RF-007): a token owned by a POR_VERIFICAR or
    NO_VERIFICADO user is rejected as invalid and the attempt is logged,
    so the services that validate tokens through this endpoint never
    resolve an unverified user.
    """

    def __init__(self, user_repository: UserRepositoryPort):
        self.user_repository = user_repository

    def execute(self, *, token: str) -> User:
        user = self.user_repository.get_by_token(token)
        if user is None or user.expireAt is None:
            raise InvalidTokenError("Invalid or expired token")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if user.expireAt < now:
            raise InvalidTokenError("Invalid or expired token")

        if user.status is not UserStatus.VERIFICADO:
            logger.warning(
                "Token verification rejected for user %s (id %s): status %s",
                user.username,
                user.id,
                user.status.value,
            )
            raise InvalidTokenError("Token belongs to a user that is not verified")

        return user
