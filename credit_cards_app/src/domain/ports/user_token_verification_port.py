"""Port for bearer token validation against the users application.

The credit cards application does not access the users database directly:
the token is validated over HTTP/REST by calling the users application
public ``GET /users/me`` endpoint, which also resolves the card owner (id
and email).
"""

from abc import ABC, abstractmethod

from domain.models.verified_user import VerifiedUser


class UserTokenVerificationPort(ABC):
    """Driven interface for validating caller bearer tokens."""

    @abstractmethod
    def verify(self, token: str) -> VerifiedUser:
        """Validate the token and return the owner (id and email).

        Raises:
            InvalidTokenError: the token is invalid or expired.
            UserVerificationUnavailableError: the users application could
                not be reached or answered with an unexpected status.
        """
