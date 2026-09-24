class CardVerificationEventError(Exception):
    """Raised when an SQS record cannot be interpreted as a verification event."""

    def __init__(self, message: str = "Invalid card verification event"):
        self.message = message
        super().__init__(self.message)


class CardNotFoundError(Exception):
    """Raised when the card referenced by an event no longer exists in the table."""

    def __init__(self, message: str = "Card not found"):
        self.message = message
        super().__init__(self.message)


class TrueNativePollingError(Exception):
    """Raised when TrueNative cannot answer the polling request or answers with an unexpected body."""

    def __init__(self, message: str = "TrueNative polling request failed"):
        self.message = message
        super().__init__(self.message)


class CardVerificationPendingError(Exception):
    """Raised when the bounded attempts are exhausted before a terminal state.

    The error propagates through the SQS handler so the invocation fails
    and the queue redelivers the event; after the maximum number of
    receives the event is moved to the dead letter queue and the card
    stays POR_VERIFICAR (documented fallback of the RF-006 pattern).
    """

    def __init__(self, message: str = "No terminal card state within the bounded attempts"):
        self.message = message
        super().__init__(self.message)
