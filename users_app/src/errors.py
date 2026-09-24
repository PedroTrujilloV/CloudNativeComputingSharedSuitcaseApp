"""Custom application exceptions."""


class TrueNativeError(Exception):
    """Raised when the TrueNative integration fails."""


class TrueNativeRequestError(TrueNativeError):
    """Raised when TrueNative answers with an HTTP error status.

    ``status_code`` carries the status returned by the provider (400 for a
    malformed or incomplete request, 401 or 403 for authentication problems
    with the secret token, 409 when a verification for the same user and
    transaction is already in progress, or any other error status).
    """

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"TrueNative answered {status_code}: {detail}")


class TrueNativeUnreachableError(TrueNativeError):
    """Raised when TrueNative cannot be reached or answers malformed data."""


class UserNotFoundError(Exception):
    """Raised when a user cannot be found."""


class UserAlreadyExistsError(Exception):
    """Raised when username or email already exists."""

    def __init__(self, message: str = "User already exists"):
        self.message = message
        super().__init__(self.message)


class UserNotVerifiedError(Exception):
    """Raised when a session token is requested for a user that is not in the
    VERIFICADO status (POR_VERIFICAR or NO_VERIFICADO)."""


class InvalidTokenError(Exception):
    """Raised when a bearer token is invalid or expired."""
