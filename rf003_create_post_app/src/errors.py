"""Custom exceptions for the RF-003 orchestrator."""


class RF003Error(Exception):
    """Base class for RF-003 orchestrator errors.

    Subclasses declare the HTTP status the router must answer with
    (``http_status``) and, when the API contract defines an exact body
    message, that message (``message``).
    """

    http_status: int | None = None
    message: str | None = None


class TokenMissingError(RF003Error):
    """The Authorization bearer token was missing or empty (HTTP 403)."""

    http_status = 403


class InvalidTokenError(RF003Error):
    """The Users service rejected the bearer token (HTTP 401)."""

    http_status = 401


class UsersServiceUnavailableError(RF003Error):
    """The Users service could not be reached (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class RoutesServiceUnavailableError(RF003Error):
    """The Routes service could not be reached or failed (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class PostsServiceUnavailableError(RF003Error):
    """The Posts service could not be reached or failed (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class RouteDatesInvalidError(RF003Error):
    """The Routes service rejected the journey dates (HTTP 412)."""

    http_status = 412
    message = "Las fechas del trayecto no son válidas"


class ExpireAtInvalidError(RF003Error):
    """The post expiration date violates the RF-003 rule (HTTP 412)."""

    http_status = 412
    message = "La fecha expiración no es válida"


class DuplicatePostError(RF003Error):
    """The user already has a post for the resolved route (HTTP 412)."""

    http_status = 412
    message = "El usuario ya tiene una publicación para la misma fecha"
