"""Domain use cases for the RF-005 orchestrator."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    """Authenticated user returned by the validation use case."""
    id: str
    username: str


class ValidateTokenUseCase:
    """Validate the bearer token before any downstream orchestration."""

    def __init__(self, user_validation):
        self.user_validation = user_validation

    def execute(self, *, token=None):
        """Resolve the authenticated user for `token`.

        Raises:
            TokenMissingError: when the token is absent/empty (HTTP 403).
            InvalidTokenError: when the Users service rejects the token
                (HTTP 401).
            UsersServiceUnavailableError: when the Users service cannot be
                reached (HTTP 503).
        """
        from errors import TokenMissingError

        if token is None or not token.strip():
            raise TokenMissingError("Missing bearer token")

        return self.user_validation.validate_token(token)


from domain.use_cases.ownership_gate_use_case import OwnershipGateUseCase
from domain.use_cases.query_post_use_case import QueryPostUseCase

__all__ = [
    "AuthenticatedUser",
    "OwnershipGateUseCase",
    "QueryPostUseCase",
    "ValidateTokenUseCase",
]


