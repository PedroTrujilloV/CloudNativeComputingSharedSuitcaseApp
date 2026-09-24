"""Value object for the caller resolved through the users application."""

from dataclasses import dataclass


@dataclass(frozen=True)
class VerifiedUser:
    """Caller validated against the users application.

    The id and the email come from the same users application API call
    (``GET /users/me``): the credit cards application never reads the
    users database directly, and the email travels in the verification
    event so the card worker can address the email notification.
    """

    id: str
    email: str = ""
