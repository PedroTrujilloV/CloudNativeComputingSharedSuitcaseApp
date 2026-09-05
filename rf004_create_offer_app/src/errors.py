"""Custom exceptions for the RF-004 orchestrator."""


class RF004Error(Exception):
    """Base class for RF-004 orchestrator errors.

    Subclasses declare the HTTP status the router must answer with
    (``http_status``) and, when the API contract defines an exact body
    message, that message (``message``). Errors whose contract body is
    empty (``N/A``) declare no message, so the router answers with an
    empty body.
    """

    http_status: int | None = None
    message: str | None = None


class TokenMissingError(RF004Error):
    """The Authorization bearer token was missing or empty (HTTP 403)."""

    http_status = 403


class InvalidTokenError(RF004Error):
    """The Users service rejected the bearer token (HTTP 401)."""

    http_status = 401


class UsersServiceUnavailableError(RF004Error):
    """The Users service could not be reached (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class PostsServiceUnavailableError(RF004Error):
    """The Posts service could not be reached (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class PostNotFoundError(RF004Error):
    """The referenced post does not exist (HTTP 404, empty body)."""

    http_status = 404


class OwnPostError(RF004Error):
    """The authenticated user owns the referenced post (HTTP 412, empty body)."""

    http_status = 412


class PostExpiredError(RF004Error):
    """The referenced post has already expired (HTTP 412, empty body)."""

    http_status = 412


class RouteNotFoundError(RF004Error):
    """The referenced route does not exist (HTTP 404, empty body)."""

    http_status = 404


class RoutesServiceUnavailableError(RF004Error):
    """The Routes service could not be reached (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class OffersServiceUnavailableError(RF004Error):
    """The Offers service could not be reached (HTTP 503)."""

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."


class ScoresServiceUnavailableError(RF004Error):
    """The Scores service could not be reached (HTTP 503).

    The score stage fails after the offer was created, so the use case
    runs the compensating action (delete the just created offer) and the
    router answers 503 with the standard message: the flow ends
    consistent, with no orphaned offer.
    """

    http_status = 503
    message = "El servicio está temporalmente fuera de servicio."
