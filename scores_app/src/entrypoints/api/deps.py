from collections.abc import Generator

from sqlalchemy.orm import Session

from adapters.database.connection import build_session_factory
from adapters.database.score_repository_adapter import (
    SQLAlchemyScoreRepositoryAdapter,
)
from domain.ports.score_repository_port import ScoreRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from domain.use_cases.count_scores_use_case import CountScoresUseCase
from domain.use_cases.get_score_by_offer_use_case import GetScoreByOfferUseCase
from domain.use_cases.get_score_use_case import GetScoreUseCase
from domain.use_cases.reset_scores_use_case import ResetScoresUseCase
from domain.use_cases.upsert_score_use_case import UpsertScoreUseCase


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session and close it afterwards."""
    session_factory = build_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_score_repository(session: Session) -> ScoreRepositoryPort:
    """Build the SQLAlchemy score repository."""
    return SQLAlchemyScoreRepositoryAdapter(session)


def get_upsert_score_use_case(session: Session) -> BaseUseCase:
    """Build the upsert-score use case."""
    return UpsertScoreUseCase(get_score_repository(session))


def get_get_score_by_offer_use_case(session: Session) -> BaseUseCase:
    """Build the get-score-by-offer use case."""
    return GetScoreByOfferUseCase(get_score_repository(session))


def get_get_score_use_case(session: Session) -> BaseUseCase:
    """Build the get-score use case."""
    return GetScoreUseCase(get_score_repository(session))


def get_count_scores_use_case(session: Session) -> BaseUseCase:
    """Build the count-scores use case."""
    return CountScoresUseCase(get_score_repository(session))


def get_reset_scores_use_case(session: Session) -> BaseUseCase:
    """Build the reset-scores use case."""
    return ResetScoresUseCase(get_score_repository(session))
