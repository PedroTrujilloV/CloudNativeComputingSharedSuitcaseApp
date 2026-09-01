"""Custom application exceptions."""


class ScoreNotFoundError(Exception):
    """Raised when a score does not exist for the given offer."""

    def __init__(self, message: str = "Score not found"):
        self.message = message
        super().__init__(self.message)
