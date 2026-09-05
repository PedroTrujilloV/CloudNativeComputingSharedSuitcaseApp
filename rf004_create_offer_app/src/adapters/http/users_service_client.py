"""HTTP client adapter for the Users service."""

import httpx

from config import Settings
from domain.ports.user_validation_port import (
    AuthenticatedUser,
    UserValidationPort,
)
from errors import (
    InvalidTokenError,
    TokenMissingError,
    UsersServiceUnavailableError,
)


class UsersServiceClient(UserValidationPort):
    """Validates bearer tokens against the Users service's ``GET /users/me``.

    The Users service (Entrega 1) already implements the exact contract the
    orchestrator needs: ``403`` when the Authorization header is missing and
    ``401`` when the token is invalid or expired. This client reuses that
    endpoint as-is and translates its responses into orchestrator errors, so
    no token logic is duplicated here.
    """

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.users_service_url,
            timeout=Settings.http_timeout,
        )

    def validate_token(self, token: str) -> AuthenticatedUser:
        """Call ``GET /users/me`` with the bearer token and map the outcome."""
        if not token:
            raise TokenMissingError("Missing bearer token")

        try:
            response = self._client.get(
                "/users/me", headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.HTTPError as exc:
            raise UsersServiceUnavailableError(
                "The Users service is temporarily unavailable"
            ) from exc

        if response.status_code == 401:
            raise InvalidTokenError("Invalid or expired token")
        if response.status_code != 200:
            raise UsersServiceUnavailableError(
                "The Users service is temporarily unavailable"
            )

        payload = response.json()
        return AuthenticatedUser(id=str(payload["id"]), username=payload["username"])

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
