class CreditCardNotFoundError(Exception):
    """Raised when a credit card cannot be found."""


class DuplicateCreditCardError(Exception):
    """Raised when the caller already stored the same credit card."""

    def __init__(self, message: str = "Duplicate credit card"):
        self.message = message
        super().__init__(self.message)


class CardExpiredError(Exception):
    """Raised when the presented card is already expired."""

    def __init__(self, message: str = "The card is already expired"):
        self.message = message
        super().__init__(self.message)


class InvalidTokenError(Exception):
    """Raised when the caller bearer token is invalid or expired."""

    def __init__(self, message: str = "Invalid or expired token"):
        self.message = message
        super().__init__(self.message)


class AuthTokenMissingError(Exception):
    """Raised when the request carries no bearer token at all."""

    def __init__(self, message: str = "Missing bearer token"):
        self.message = message
        super().__init__(self.message)


class UserVerificationUnavailableError(Exception):
    """Raised when the user verification service cannot answer."""

    def __init__(self, message: str = "User verification service unavailable"):
        self.message = message
        super().__init__(self.message)


class TrueNativeRegistrationError(Exception):
    """Raised when TrueNative cannot register the card or generate the token."""

    def __init__(self, message: str = "TrueNative card registration failed"):
        self.message = message
        super().__init__(self.message)
