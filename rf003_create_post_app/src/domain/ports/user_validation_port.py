"""Port (contract) for validating bearer tokens against the Users service.

The orchestrator must not duplicate token logic: validation is delegated to
the Users service's existing ``GET /users/me`` endpoint (Entrega 1, reused
as-is).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    """The user owning a valid bearer token."""

    id: str
    username: str


class UserValidationPort(ABC):
    """Validates a bearer token by calling the Users service."""

    @abstractmethod
    def validate_token(self, token: str) -> AuthenticatedUser:
        """Resolve the user for ``token``.

        Raises:
            TokenMissingError: the Authorization header was absent/empty.
            InvalidTokenError: the Users service rejected the token (401).
            UsersServiceUnavailableError: the Users service could not be
                reached (network error / 5xx).
        """
