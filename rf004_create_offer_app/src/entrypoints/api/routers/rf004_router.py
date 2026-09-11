"""RF-004 router: POST /rf004/posts/{post_id}/offers (full offer creation flow).

The endpoint validates the bearer token and the request body first, then
runs the post-level preconditions. When every gate passes, it orchestrates
the full offer creation flow: create the offer, fetch the route and
calculate the score, persist the score, and return a 201 response.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domain.models.schemas import RF004CreateOfferRequest
from domain.use_cases.create_offer_use_case import CreateOfferUseCase
from domain.use_cases.offer_preconditions_use_case import OfferPreconditionsUseCase
from domain.use_cases.validate_token_use_case import ValidateTokenUseCase
from entrypoints.api.deps import (
    get_create_offer_use_case,
    get_offer_preconditions_use_case,
    get_validate_token_use_case,
)
from errors import (
    InvalidTokenError,
    OffersServiceUnavailableError,
    RF004Error,
    RouteNotFoundError,
    RoutesServiceUnavailableError,
    ScoresServiceUnavailableError,
    TokenMissingError,
)

bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/rf004")


@router.get("/ping", response_class=PlainTextResponse)
def health_check():
    """Healthcheck endpoint."""
    return "pong"


def _error_response(exc: RF004Error) -> JSONResponse | Response:
    """Map an orchestrator error onto its documented HTTP answer.

    Errors whose contract body is empty (``N/A`` in the spec) declare no
    message and produce an empty body.
    """
    status = exc.http_status or 500
    if exc.message is not None:
        return JSONResponse(status_code=status, content={"msg": exc.message})
    return Response(status_code=status)


@router.post("/posts/{post_id}/offers", status_code=201)
def create_offer(
    post_id: str,
    payload: RF004CreateOfferRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    validate_token: ValidateTokenUseCase = Depends(get_validate_token_use_case),
    preconditions: OfferPreconditionsUseCase = Depends(
        get_offer_preconditions_use_case
    ),
    create_offer_use_case: CreateOfferUseCase = Depends(get_create_offer_use_case),
):
    """Create an offer (RF-004).

    Validates the bearer token and the request body, then checks the
    post-level preconditions (post exists, not owned by the caller, not
    expired). When every gate passes, orchestrates the full offer creation
    flow (create offer, fetch the route and calculate the score, persist
    the score) and returns a 201 response. Error mapping:
      - 403 empty body: missing bearer token
      - 401 empty body: invalid/expired token
      - 400 empty body: malformed request body (handled in ``main.py``)
      - 404 empty body: the post does not exist (or its route is missing;
        in both cases no offer remains, the offer is compensated when the
        route is missing)
      - 412 empty body: own post, or already expired post
      - 503 ``{"msg": ...}``: Users, Posts, Routes, Offers, or Scores
        service unreachable (when the failure happens after the offer was
        created, the offer is first compensated)
      - 201: offer created and its score persisted
    """
    token = credentials.credentials if credentials is not None else None
    try:
        user = validate_token.execute(token=token)
        post = preconditions.execute(user=user, post_id=post_id)
    except TokenMissingError:
        return Response(status_code=403)
    except InvalidTokenError:
        return Response(status_code=401)
    except RF004Error as exc:
        return _error_response(exc)

    # Every gate passed. Orchestrate the full offer creation flow.
    # Routes, Offers, and Scores are hard dependencies: when any of them
    # is unreachable the request cannot be completed, so the endpoint
    # answers 503 with the documented message. When the score stage fails
    # after the offer was created, the use case has already compensated
    # (deleted the just created offer), so the 503 leaves no orphaned
    # data behind.
    try:
        result = create_offer_use_case.execute(
            post=post,
            user_id=user.id,
            payload=payload,
        )
    except (
        OffersServiceUnavailableError,
        RoutesServiceUnavailableError,
        ScoresServiceUnavailableError,
        RouteNotFoundError,
    ) as exc:
        return _error_response(exc)

    data = {
        "id": result["id"],
        "userId": result["userId"],
        "createdAt": result["createdAt"],
        "postId": result["postId"],
    }

    # The flow only reaches this point when every write succeeded: the
    # offer exists and its score is persisted (a score stage failure is
    # compensated and answered 503 above).
    return JSONResponse(
        status_code=201,
        content={
            "msg": "Oferta creada exitosamente.",
            "data": data,
        },
    )
