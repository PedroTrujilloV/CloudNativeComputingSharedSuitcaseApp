"""Custom application exceptions."""


class UserNotFoundError(Exception):
    """Raised when a user cannot be found."""


class UserAlreadyExistsError(Exception):
    """Raised when username or email already exists."""

    def __init__(self, message: str = "User already exists"):
        self.message = message
        super().__init__(self.message)


class InvalidTokenError(Exception):
    """Raised when a bearer token is invalid or expired."""
