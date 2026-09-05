"""Authentication gate use case for RF-004.

RF-004 is a user-only operation: the bearer token must be validated
against the Users service before any state-changing downstream call
(offer creation) begins.
"""

from domain.ports.user_validation_port import (
    AuthenticatedUser,
    UserValidationPort,
)
from errors import TokenMissingError


class ValidateTokenUseCase:
    """Validate the bearer token before any downstream orchestration."""

    def __init__(self, user_validation: UserValidationPort):
        self.user_validation = user_validation

    def execute(self, *, token: str | None) -> AuthenticatedUser:
        """Resolve the authenticated user for ``token``.

        Raises:
            TokenMissingError: when the token is absent/empty (HTTP 403).
            InvalidTokenError: when the Users service rejects the token
                (HTTP 401).
            UsersServiceUnavailableError: when the Users service cannot be
                reached (HTTP 503).
        """
        if token is None or not token.strip():
            raise TokenMissingError("Missing bearer token")

        return self.user_validation.validate_token(token)
