"""RF-005 router: GET /rf005/posts/{id} (auth + authorization gate).

The endpoint validates the bearer token and checks post ownership first,
answering with 403/401 for missing/invalid tokens and 403/404 for missing
posts or non-owner access, before any data aggregation occurs.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domain.use_cases import ValidateTokenUseCase
from domain.use_cases.ownership_gate_use_case import OwnershipGateUseCase
from domain.use_cases.query_post_use_case import QueryPostUseCase
from entrypoints.api.deps import (
    get_ownership_gate_use_case,
    get_query_post_use_case,
    get_validate_token_use_case,
)
from errors import (
    AggregationFailureError,
    InvalidTokenError,
    OffersServiceUnavailableError,
    PostNotFoundError,
    PostsServiceUnavailableError,
    RF005Error,
    RoutesServiceUnavailableError,
    TokenMissingError,
    UserNotOwnerError,
    UsersServiceUnavailableError,
)

bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/rf005")


@router.get("/ping", response_class=PlainTextResponse)
def health_check():
    """Healthcheck endpoint."""
    return "pong"


def _error_response(exc: RF005Error) -> JSONResponse:
    """Map an orchestrator error onto its documented HTTP answer."""
    status = exc.http_status or 500
    if exc.message is not None:
        return JSONResponse(status_code=status, content={"msg": exc.message})
    return Response(status_code=status)


@router.get("/posts/{post_id}", status_code=200)
def query_post(
    post_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    validate_token: ValidateTokenUseCase = Depends(get_validate_token_use_case),
    ownership_gate: OwnershipGateUseCase = Depends(get_ownership_gate_use_case),
    query_post_use_case: QueryPostUseCase = Depends(get_query_post_use_case),
):
    """Query a post (RF-005).

    Validates the bearer token and checks post ownership, then aggregates
    the post, its route, and its offers. Error mapping:
      - 403 empty body: missing bearer token
      - 401 empty body: invalid/expired token
      - 404 empty body: post does not exist
      - 403 empty body: authenticated user is not the post owner
      - 503 {"msg": ...}: any downstream service unreachable (Users,
        Posts, Routes, or Offers). Score unavailability never reaches
        this mapping: per the RF-005 resilience requirement it degrades
        to ``score: null`` for the affected offer and the request still
        returns 200.
    """
    token = credentials.credentials if credentials is not None else None
    try:
        user = validate_token.execute(token=token)
        post = ownership_gate.execute(user=user, post_id=post_id)

        # Aggregate the full response (post fields + route + offers +
        # scores). Score lookups are resilient inside the use case.
        result = query_post_use_case.execute(
            post=post, post_id=post_id, route_id=post.routeId
        )
        return JSONResponse(
            status_code=200,
            content={"data": result.data},
        )
    except TokenMissingError:
        return Response(status_code=403)
    except InvalidTokenError:
        return Response(status_code=401)
    except PostNotFoundError:
        return Response(status_code=404)
    except UserNotOwnerError:
        return Response(status_code=403)
    except (
        AggregationFailureError,
        UsersServiceUnavailableError,
        PostsServiceUnavailableError,
        RoutesServiceUnavailableError,
        OffersServiceUnavailableError,
    ) as exc:
        return JSONResponse(status_code=503, content={"msg": exc.message})
    except Exception:
        # Any unexpected failure inside the aggregation (including a
        # missing route record) is an integration failure for the
        # client: answer with the documented 503 body instead of a
        # generic 500.
        return JSONResponse(
            status_code=503,
            content={"msg": "El servicio está temporalmente fuera de servicio."},
        )
