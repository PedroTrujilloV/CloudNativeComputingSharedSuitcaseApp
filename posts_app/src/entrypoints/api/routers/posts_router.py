import re
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from adapters.database.repository import PublicationRepository
from domain.use_cases.create_publication import CreatePublicationUseCase
from entrypoints.api.schemas.post_schema import (
    CountPostsResponse,
    CreatePostRequest,
    CreatePostResponse,
    MessageResponse,
    PostResponse,
)

router = APIRouter(prefix="/posts")

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _is_valid_uuid(value: str) -> bool:
    """Return True when value is a canonical UUID string."""
    return bool(UUID_PATTERN.match(value))


def _parse_expire_at(value: str) -> datetime:
    """Parse an ISO 8601 expireAt into a naive UTC datetime.

    Clients send an offset-aware timestamp ("...Z" from Date.toISOString()).
    The stored values are naive UTC, so an aware input is converted before it
    reaches any comparison — mixing the two raises TypeError.
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _to_iso_utc(value: datetime) -> str:
    """Serialise a stored naive UTC datetime as an explicit UTC timestamp.

    Without the "Z" a client parses the string as local time — `new Date(...)`
    in a browser at UTC-5 would place an expiry five hours away from the one
    `GET /posts?expire=true` filters on.
    """
    return value.isoformat() + "Z"


def _to_response(publication) -> PostResponse:
    """Map a persisted publication onto the API contract's Publicación object."""
    return PostResponse(
        id=publication.id,
        route_id=publication.route_id,
        user_id=publication.user_id,
        expire_at=_to_iso_utc(publication.expire_at),
        created_at=_to_iso_utc(publication.created_at),
    )


@router.get("/ping", response_class=PlainTextResponse)
async def ping():
    """Health check endpoint."""
    return "pong"


@router.post("", status_code=201)
async def create_post(request: CreatePostRequest, response: Response):
    """
    Create a new publication.

    Request body:
    {
      "routeId": string (uuid),
      "userId": string (uuid),
      "expireAt": string (ISO format)
    }

    Returns:
    - 201: {"id": string, "userId": string, "createdAt": string}
    - 400: If any required field is missing or malformed
    - 412: If expireAt is not in the future

    Raises:
        ValueError: If expireAt validation fails → 412
    """
    try:
        # routeId and userId must be uuid strings
        if not _is_valid_uuid(request.route_id) or not _is_valid_uuid(request.user_id):
            response.status_code = 400
            return {"msg": "routeId y userId deben ser UUID válidos"}

        # Parse expireAt string to datetime
        try:
            expire_at = _parse_expire_at(request.expire_at)
        except (ValueError, TypeError):
            response.status_code = 400
            return {"msg": "expireAt no tiene un formato de fecha válido"}

        # Create publication via use case
        repository = PublicationRepository()
        use_case = CreatePublicationUseCase(repository)
        publication = use_case.execute(
            route_id=request.route_id,
            user_id=request.user_id,
            expire_at=expire_at,
        )

        # Return 201 with correct format
        return CreatePostResponse(
            id=publication.id,
            user_id=publication.user_id,
            created_at=_to_iso_utc(publication.created_at),
        )

    except ValueError:
        # expireAt validation failed
        response.status_code = 412
        return {"msg": "La fecha expiración no es válida"}


@router.get("", response_model=list[PostResponse], status_code=200)
async def list_posts(
    expire: str | None = Query(None),
    route: str | None = Query(None),
    owner: str | None = Query(None),
):
    """
    List publications, optionally filtered.

    Query params (all optional, combined with AND semantics):
    - expire: "true" for expired publications, "false" for active ones
    - route: routeId to filter by
    - owner: userId to filter by

    Returns:
    - 200: array of Publicación objects
    - 400: If any filter value is malformed
    """
    expire_status = None
    if expire is not None:
        normalized = expire.lower()
        if normalized not in ("true", "false"):
            return JSONResponse(status_code=400, content={"msg": "El parámetro expire debe ser 'true' o 'false'"})

        expire_status = "expired" if normalized == "true" else "not_expired"

    if route is not None and not _is_valid_uuid(route):
        return JSONResponse(status_code=400, content={"msg": "El parámetro route debe ser un UUID válido"})

    if owner is not None and not _is_valid_uuid(owner):
        return JSONResponse(status_code=400, content={"msg": "El parámetro owner debe ser un UUID válido"})

    repository = PublicationRepository()
    publications = repository.list(
        route_id=route,
        user_id=owner,
        expire_status=expire_status,
    )

    return [_to_response(publication) for publication in publications]


@router.get("/count", response_model=CountPostsResponse, status_code=200)
async def count_posts():
    """
    Return how many publications are stored.

    Returns:
    - 200: {"count": int}
    """
    repository = PublicationRepository()
    return CountPostsResponse(count=repository.count())


@router.post("/reset", response_model=MessageResponse, status_code=200)
async def reset_posts():
    """
    Delete every publication.

    Returns:
    - 200: {"msg": "Todos los datos fueron eliminados"}
    """
    repository = PublicationRepository()
    repository.delete_all()
    return MessageResponse(msg="Todos los datos fueron eliminados")


@router.get("/{post_id}", response_model=PostResponse, status_code=200)
async def get_post_by_id(post_id: str):
    """
    Retrieve a single publication.

    Returns:
    - 200: the Publicación object
    - 400: If post_id is not a valid uuid string
    - 404: If no publication exists with that id
    """
    if not _is_valid_uuid(post_id):
        return JSONResponse(status_code=400, content={"msg": "El id debe ser un UUID válido"})

    repository = PublicationRepository()
    publication = repository.get_by_id(post_id)

    if publication is None:
        return JSONResponse(status_code=404, content={"msg": "No existe una publicación con ese id"})

    return _to_response(publication)


@router.delete("/{post_id}", response_model=MessageResponse, status_code=200)
async def delete_post(post_id: str):
    """
    Delete a single publication.

    Returns:
    - 200: {"msg": "la publicación fue eliminada"}
    - 400: If post_id is not a valid uuid string
    - 404: If no publication exists with that id
    """
    if not _is_valid_uuid(post_id):
        return JSONResponse(status_code=400, content={"msg": "El id debe ser un UUID válido"})

    repository = PublicationRepository()
    if not repository.delete(post_id):
        return JSONResponse(status_code=404, content={"msg": "No existe una publicación con ese id"})

    return MessageResponse(msg="la publicación fue eliminada")
