from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.database.models import Base
from adapters.database.score_repository_adapter import (
    SQLAlchemyScoreRepositoryAdapter,
)
from domain.models.score import Score


@pytest.fixture
def repository():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = SQLAlchemyScoreRepositoryAdapter(session)
    yield repo
    session.close()


def _build_score(
    *, offer_id: str = "22222222-2222-2222-2222-222222222222", value: float = 150.5
) -> Score:
    now = datetime.now(timezone.utc)
    return Score(offer_id=offer_id, value=value, created_at=now, updated_at=now)


def test_upsert_persists_new_score(repository):
    score = _build_score()

    created = repository.upsert(score)

    assert created.offer_id == score.offer_id
    assert created.value == score.value
    assert created.id == score.id
    assert created.created_at == score.created_at
    assert created.updated_at == score.updated_at
    assert repository.count() == 1


def test_get_by_offer_id_returns_none_when_no_score_exists(repository):
    """A missing score must read as null (None), never as an error."""
    assert repository.get_by_offer_id("99999999-9999-9999-9999-999999999999") is None


def test_get_by_offer_id_returns_persisted_score(repository):
    score = _build_score()

    repository.upsert(score)

    fetched = repository.get_by_offer_id(score.offer_id)

    assert fetched is not None
    assert fetched.offer_id == score.offer_id
    assert fetched.value == score.value


def test_get_by_id_returns_persisted_score(repository):
    score = _build_score()
    repository.upsert(score)

    fetched = repository.get_by_id(score.id)

    assert fetched is not None
    assert fetched.id == score.id
    assert fetched.offer_id == score.offer_id
    assert fetched.value == score.value


def test_get_by_id_returns_none_when_score_absent(repository):
    assert repository.get_by_id("99999999-9999-9999-9999-999999999999") is None


def test_upsert_updates_existing_score_for_same_offer(repository):
    """Score values can be updated over time for the same offer."""
    first = _build_score(value=100.0)
    repository.upsert(first)

    now = datetime.now(timezone.utc)
    second = Score(
        offer_id=first.offer_id, value=250.75, created_at=now, updated_at=now
    )
    updated = repository.upsert(second)

    assert repository.count() == 1
    assert updated.offer_id == first.offer_id
    assert updated.value == 250.75
    assert updated.updated_at == now

    fetched = repository.get_by_offer_id(first.offer_id)
    assert fetched is not None
    assert fetched.value == 250.75


def test_upsert_creates_independent_rows_per_offer(repository):
    offer_one = "22222222-2222-2222-2222-222222222222"
    offer_two = "33333333-3333-3333-3333-333333333333"

    repository.upsert(_build_score(offer_id=offer_one, value=10.0))
    repository.upsert(_build_score(offer_id=offer_two, value=20.0))

    assert repository.count() == 2
    assert repository.get_by_offer_id(offer_one).value == 10.0
    assert repository.get_by_offer_id(offer_two).value == 20.0


def test_delete_removes_score_for_offer(repository):
    score = _build_score()
    repository.upsert(score)

    assert repository.delete(score.offer_id) is True
    assert repository.count() == 0
    assert repository.get_by_offer_id(score.offer_id) is None


def test_delete_returns_false_when_score_absent(repository):
    assert repository.delete("99999999-9999-9999-9999-999999999999") is False


def test_delete_all_removes_every_score(repository):
    repository.upsert(_build_score(offer_id="11111111-1111-1111-1111-111111111111"))
    repository.upsert(_build_score(offer_id="22222222-2222-2222-2222-222222222222"))

    deleted_items = repository.delete_all()

    assert deleted_items == 2
    assert repository.count() == 0
