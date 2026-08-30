class OfferNotFoundError(Exception):
    """Raised when an offer cannot be found."""


class InvalidOfferError(Exception):
    """Raised when an offer violates business rules."""

    def __init__(self, message: str = "Invalid offer"):
        self.message = message
        super().__init__(self.message)
