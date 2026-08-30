"""Custom application exceptions."""


class RouteNotFoundError(Exception):
    """Raised when a route cannot be found."""
    pass


class RouteAlreadyExistsError(Exception):
    """Raised when route details already exist."""

    def __init__(self, message: str = "Route already exists"):
        self.message = message
        super().__init__(self.message)