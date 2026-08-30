from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import ValidationError

from domain.models.offer import Offer, OfferCreateRequest, OfferCreateResponse, OfferResponse
from domain.use_cases.base_use_case import BaseUseCase
from entrypoints.api.deps import (
    get_count_offers_use_case,
    get_create_offer_use_case,
    get_db_session,
    get_delete_all_offers_use_case,
    get_delete_offer_use_case,
    get_get_offer_use_case,
    get_list_offers_use_case,
)
from errors import InvalidOfferError, OfferNotFoundError
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/offers")


@router.get("/ping", response_class=PlainTextResponse)
def health_check():
    """Healthcheck endpoint."""
    return "pong"


@router.post("", response_model=OfferCreateResponse, status_code=201)
def create_offer(
    offer: OfferCreateRequest,
    session: Session = Depends(get_db_session),
):
    """Create a new offer."""
    use_case: BaseUseCase = get_create_offer_use_case(session)
    now = datetime.now(timezone.utc)
    try:
        created = use_case.execute(
            Offer(
                id=uuid4(),
                post_id=offer.post_id,
                user_id=offer.user_id,
                description=offer.description,
                size=offer.size,
                fragile=offer.fragile,
                offer=offer.offer,
                created_at=now,
            )
        )
    except (InvalidOfferError, ValidationError):
        return Response(status_code=412)

    return OfferCreateResponse(
        id=created.id,
        user_id=created.user_id,
        created_at=created.created_at,
    )


@router.get("", response_model=list[OfferResponse])
def list_offers(
    post: str | None = None,
    owner: str | None = None,
    session: Session = Depends(get_db_session),
):
    """List offers, optionally filtered by post and owner (AND semantics)."""
    post_id = _parse_uuid(post)
    if post is not None and post_id is None:
        return Response(status_code=400)

    user_id = _parse_uuid(owner)
    if owner is not None and user_id is None:
        return Response(status_code=400)

    use_case: BaseUseCase = get_list_offers_use_case(session)
    offers = use_case.execute(post_id=post_id, user_id=user_id)
    return [_to_response(offer) for offer in offers]


@router.get("/count")
def count_offers(session: Session = Depends(get_db_session)):
    """Return the number of stored offers."""
    use_case: BaseUseCase = get_count_offers_use_case(session)
    return {"count": use_case.execute()}


@router.get("/{offer_id}", response_model=OfferResponse)
def get_offer(offer_id: str, session: Session = Depends(get_db_session)):
    """Retrieve a single offer by its id."""
    parsed = _parse_uuid(offer_id)
    if parsed is None:
        return Response(status_code=400)

    use_case: BaseUseCase = get_get_offer_use_case(session)
    try:
        offer = use_case.execute(parsed)
    except OfferNotFoundError:
        return Response(status_code=404)

    return _to_response(offer)


@router.delete("/{offer_id}")
def delete_offer(offer_id: str, session: Session = Depends(get_db_session)):
    """Delete a single offer by its id."""
    parsed = _parse_uuid(offer_id)
    if parsed is None:
        return Response(status_code=400)

    use_case: BaseUseCase = get_delete_offer_use_case(session)
    try:
        use_case.execute(parsed)
    except OfferNotFoundError:
        return Response(status_code=404)

    return {"msg": "la oferta fue eliminada"}


@router.post("/reset", response_model=dict)
def delete_all_offers(session: Session = Depends(get_db_session)):
    """Delete all offers."""
    use_case: BaseUseCase = get_delete_all_offers_use_case(session)
    use_case.execute()
    return {"msg": "Todos los datos fueron eliminados"}


def _parse_uuid(value: str | None) -> UUID | None:
    """Parse a string into a UUID, or return None if malformed/empty."""
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _to_response(offer: Offer) -> OfferResponse:
    """Convert a domain offer into its API response representation."""
    return OfferResponse(
        id=offer.id,
        post_id=offer.post_id,
        user_id=offer.user_id,
        description=offer.description,
        size=offer.size,
        fragile=offer.fragile,
        offer=offer.offer,
        created_at=offer.created_at,
    )