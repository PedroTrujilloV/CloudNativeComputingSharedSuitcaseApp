"""HTTP adapter that validates bearer tokens against the users application."""

import json
from collections.abc import Callable

from httpx2 import Client, HTTPError

from config import Settings
from domain.models.verified_user import VerifiedUser
from domain.ports.user_token_verification_port import UserTokenVerificationPort
from errors import InvalidTokenError, UserVerificationUnavailableError


class UsersAppUserVerificationAdapter(UserTokenVerificationPort):
    """Validates tokens through the users application public API.

    The credit cards application never reads the users database directly;
    the token is checked by calling ``GET /users/me`` of the users
    application, which also resolves the card owner (id and email, the
    email being the recipient of the card result notification). An
    invalid or expired token surfaces as ``InvalidTokenError`` (HTTP 401),
    and a users application that cannot answer surfaces as
    ``UserVerificationUnavailableError`` (HTTP 502).
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        client_factory: Callable[[], Client] | None = None,
    ):
        self.base_url = (base_url or Settings.users_app_url).rstrip("/")
        self.timeout = timeout if timeout is not None else Settings.http_timeout_seconds
        self.client_factory = client_factory

    def _new_client(self) -> Client:
        """Create the HTTP client used for the call (test seam included)."""
        if self.client_factory is not None:
            return self.client_factory()
        return Client(timeout=self.timeout)

    def verify(self, token: str) -> VerifiedUser:
        """Validate the token and return the owner (id and email)."""
        try:
            with self._new_client() as client:
                response = client.get(
                    f"{self.base_url}/users/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except HTTPError as exc:
            raise UserVerificationUnavailableError(
                "The users application could not be reached"
            ) from exc

        if response.status_code == 200:
            return self._extract_verified_user(response.text)
        if response.status_code in (401, 403):
            raise InvalidTokenError()
        raise UserVerificationUnavailableError(
            f"The users application answered with status {response.status_code}"
        )

    @staticmethod
    def _extract_verified_user(body: str) -> VerifiedUser:
        """Read the owner id and email from the users application answer."""
        try:
            data = json.loads(body)
        except ValueError:
            raise UserVerificationUnavailableError(
                "The users application answered with an unexpected body"
            ) from None
        if not isinstance(data, dict):
            raise UserVerificationUnavailableError(
                "The users application answered with an unexpected body"
            )
        user_id = data.get("id")
        if not user_id:
            raise UserVerificationUnavailableError(
                "The users application answer has no user id"
            )
        email = data.get("email")
        return VerifiedUser(id=str(user_id), email=str(email) if email else "")
