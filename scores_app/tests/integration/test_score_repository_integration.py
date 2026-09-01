"""Integration tests for the Score persistence layer.

Run against a real database engine (SQLite in-process by default; point
``SCORES_INTEGRATION_DATABASE_URL`` at a PostgreSQL instance to run the same
suite against a real server):

    SCORES_INTEGRATION_DATABASE_URL=postgresql+psycopg://scores_user:***@localhost:5432/scores_db \
        poetry run pytest tests/integration -v
"""

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from adapters.database.models import Base
from adapters.database.score_repository_adapter import (
    SQLAlchemyScoreRepositoryAdapter,
)
from domain.models.score import Score

INTEGRATION_DATABASE_URL = os.getenv("SCORES_INTEGRATION_DATABASE_URL")


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


@pytest.fixture
def repository():
    url = INTEGRATION_DATABASE_URL or "sqlite:///:memory:"
    engine = create_engine(url, **_engine_kwargs(url))

    if INTEGRATION_DATABASE_URL:
        # Real server: create the schema and start from a clean table.
        with engine.begin() as connection:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("DELETE FROM scores"))
    else:
        Base.metadata.create_all(bind=engine)

    session = sessionmaker(bind=engine)()
    yield SQLAlchemyScoreRepositoryAdapter(session)
    session.close()
    engine.dispose()


def test_integration_persist_and_retrieve_score(repository):
    now = datetime.now(timezone.utc)
    score = Score(
        offer_id="550e8400-e29b-41d4-a716-446655440000",
        value=120.25,
        created_at=now,
        updated_at=now,
    )

    repository.upsert(score)

    fetched = repository.get_by_offer_id(score.offer_id)

    assert fetched is not None
    assert fetched.offer_id == score.offer_id
    assert fetched.value == pytest.approx(120.25)
    assert fetched.created_at == score.created_at


def test_integration_missing_score_returns_none(repository):
    assert repository.get_by_offer_id("550e8400-e29b-41d4-a716-446655440001") is None


def test_integration_update_score_over_time(repository):
    now = datetime.now(timezone.utc)
    repository.upsert(
        Score(
            offer_id="660e8400-e29b-41d4-a716-446655440001",
            value=50.0,
            created_at=now,
            updated_at=now,
        )
    )

    later = now + timedelta(seconds=1)
    repository.upsert(
        Score(
            offer_id="660e8400-e29b-41d4-a716-446655440001",
            value=75.5,
            created_at=now,
            updated_at=later,
        )
    )

    fetched = repository.get_by_offer_id("660e8400-e29b-41d4-a716-446655440001")

    assert fetched is not None
    assert fetched.value == pytest.approx(75.5)
    assert fetched.updated_at == later
    assert repository.count() == 1
