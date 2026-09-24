"""Custom application exceptions."""


class CallbackError(Exception):
    """Raised when the verification callback processing fails."""


class SignatureMismatchError(CallbackError):
    """Raised when the callback signature does not match the payload."""


class UserNotFoundError(CallbackError):
    """Raised when the Users service does not know the user identifier."""

    def __init__(self, message: str = "User not found"):
        self.message = message
        super().__init__(self.message)


class UsersServiceUnavailableError(CallbackError):
    """Raised when the Users service cannot be reached or answers an error."""


class EmailNotificationError(CallbackError):
    """Raised when the email notification provider rejects the message."""
