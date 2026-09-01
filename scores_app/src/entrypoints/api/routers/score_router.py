from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy.orm import Session

from domain.models.score import (
    Score,
    ScoreCreateRequest,
    ScoreCreateResponse,
    ScoreFullResponse,
    ScoreGetResponse,
    ScoreUpdateResponse,
)
from domain.use_cases.base_use_case import BaseUseCase
from entrypoints.api.deps import (
    get_count_scores_use_case,
    get_db_session,
    get_get_score_by_offer_use_case,
    get_get_score_use_case,
    get_reset_scores_use_case,
    get_upsert_score_use_case,
)
from errors import ScoreNotFoundError

router = APIRouter(prefix="/scores")


@router.get("/ping", response_class=PlainTextResponse)
def health_check():
    """Healthcheck endpoint."""
    return "pong"


@router.post("")
def upsert_score(
    payload: ScoreCreateRequest,
    session: Session = Depends(get_db_session),
):
    """Create the score for an offer, or update it if it already exists."""
    now = datetime.now(timezone.utc)

    get_by_offer: BaseUseCase = get_get_score_by_offer_use_case(session)
    already_exists = get_by_offer.execute(str(payload.offer_id)) is not None

    upsert: BaseUseCase = get_upsert_score_use_case(session)
    score = upsert.execute(
        Score(
            offer_id=str(payload.offer_id),
            value=payload.score,
            created_at=now,
            updated_at=now,
        )
    )

    if already_exists:
        response = ScoreUpdateResponse(
            id=score.id,
            offer_id=score.offer_id,
            score=score.value,
            updated_at=score.updated_at,
        )
        return JSONResponse(
            status_code=200,
            content=response.model_dump(by_alias=True, mode="json"),
        )

    response = ScoreCreateResponse(
        id=score.id,
        offer_id=score.offer_id,
        score=score.value,
        created_at=score.created_at,
    )
    return JSONResponse(
        status_code=201,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@router.get("")
def get_score_by_offer(
    offer_id: UUID = Query(alias="offerId"),
    session: Session = Depends(get_db_session),
):
    """Return the score for an offer (null-safe when no score exists yet)."""
    use_case: BaseUseCase = get_get_score_by_offer_use_case(session)
    score = use_case.execute(str(offer_id))

    if score is None:
        return JSONResponse(
            status_code=200,
            content={"offerId": str(offer_id), "score": None},
        )

    return ScoreGetResponse(
        id=score.id,
        offer_id=score.offer_id,
        score=score.value,
        created_at=score.created_at,
    )


@router.get("/count")
def count_scores(session: Session = Depends(get_db_session)):
    """Return the number of stored scores."""
    use_case: BaseUseCase = get_count_scores_use_case(session)
    return {"count": use_case.execute()}


@router.post("/reset")
def reset_scores(session: Session = Depends(get_db_session)):
    """Delete all stored scores."""
    use_case: BaseUseCase = get_reset_scores_use_case(session)
    use_case.execute()
    return {"msg": "All data was deleted"}


@router.get("/{score_id}", response_model=ScoreFullResponse)
def get_score(score_id: str, session: Session = Depends(get_db_session)):
    """Retrieve a single score by its id."""
    if _parse_uuid(score_id) is None:
        return Response(status_code=400)

    use_case: BaseUseCase = get_get_score_use_case(session)
    try:
        score = use_case.execute(score_id)
    except ScoreNotFoundError:
        return Response(status_code=404)

    return ScoreFullResponse(
        id=score.id,
        offer_id=score.offer_id,
        score=score.value,
        created_at=score.created_at,
        updated_at=score.updated_at,
    )


def _parse_uuid(value: str) -> UUID | None:
    """Parse a string into a UUID, or return None if malformed."""
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None
