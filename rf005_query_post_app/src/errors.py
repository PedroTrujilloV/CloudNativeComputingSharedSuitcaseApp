"""Custom exceptions for the RF-005 orchestrator."""


class RF005Error(Exception):
    """Base class for RF-005 orchestrator errors.

    Subclasses declare the HTTP status the router must answer with
    (`http_status`) and, when the API contract defines an exact body
    message, that message (`message`).
    """

    http_status: int | None = None
    message: str | None = None


class TokenMissingError(RF005Error):
    """The Authorization bearer token was missing or empty (HTTP 403)."""

    http_status = 403


class InvalidTokenError(RF005Error):
    """The Users service rejected the bearer token (HTTP 401)."""

    http_status = 401


class PostNotFoundError(RF005Error):
    """The referenced post does not exist (HTTP 404, empty body)."""

    http_status = 404


class RouteNotFoundError(RF005Error):
    """The referenced route does not exist (HTTP 404, empty body)."""

    http_status = 404


class UserNotOwnerError(RF005Error):
    """The authenticated user is not the post owner (HTTP 403, empty body)."""

    http_status = 403


class AggregationFailureError(RF005Error):
    """Data aggregation failed after gates passed (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class UsersServiceUnavailableError(RF005Error):
    """The Users service could not be reached (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class PostsServiceUnavailableError(RF005Error):
    """The Posts service could not be reached (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class RoutesServiceUnavailableError(RF005Error):
    """The Routes service could not be reached (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class OffersServiceUnavailableError(RF005Error):
    """The Offers service could not be reached (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class ScoresServiceUnavailableError(RF005Error):
    """The Score service could not be reached (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."
