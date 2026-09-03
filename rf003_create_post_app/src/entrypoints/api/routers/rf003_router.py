"""RF-003 router: POST /rf003/posts (auth gate + core orchestration).

The endpoint validates the bearer token and the request body first, then
runs the core orchestration: route find-or-create by ``flightId``, post
``expireAt`` validation, duplicate-post check and post creation, answering
with the documented 201 shape on success.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domain.models.schemas import RF003CreatePostRequest
from domain.use_cases.create_post_use_case import CreatePostUseCase
from domain.use_cases.validate_token_use_case import ValidateTokenUseCase
from entrypoints.api.deps import (
    get_create_post_use_case,
    get_validate_token_use_case,
)
from errors import (
    InvalidTokenError,
    RF003Error,
    TokenMissingError,
)

bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/rf003")


@router.get("/ping", response_class=PlainTextResponse)
def health_check():
    """Healthcheck endpoint."""
    return "pong"


def _error_response(exc: RF003Error) -> JSONResponse:
    """Map an orchestrator error onto its documented HTTP answer."""
    status = exc.http_status or 500
    if exc.message is not None:
        return JSONResponse(status_code=status, content={"msg": exc.message})
    return Response(status_code=status)


@router.post("/posts", status_code=201)
def create_post(
    payload: RF003CreatePostRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    validate_token: ValidateTokenUseCase = Depends(get_validate_token_use_case),
    create_post_uc: CreatePostUseCase = Depends(get_create_post_use_case),
):
    """Create a post (RF-003).

    Validates the bearer token and the request body, then orchestrates the
    route find-or-create and the post creation. Error mapping:
      - 403 empty body: missing bearer token
      - 401 empty body: invalid/expired token
      - 400 empty body: malformed request body (handled in ``main.py``)
      - 412 ``{"msg": ...}``: route dates, expireAt or duplicate post
      - 503 ``{"msg": ...}``: any downstream service unreachable
    """
    token = credentials.credentials if credentials is not None else None
    try:
        user = validate_token.execute(token=token)
        body = create_post_uc.execute(user=user, payload=payload)
    except TokenMissingError:
        return Response(status_code=403)
    except InvalidTokenError:
        return Response(status_code=401)
    except RF003Error as exc:
        return _error_response(exc)

    return JSONResponse(status_code=201, content=body)
