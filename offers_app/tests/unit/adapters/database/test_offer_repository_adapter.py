from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from adapters.database.models import Base
from adapters.database.offer_repository_adapter import SQLAlchemyOfferRepositoryAdapter
from domain.models.offer import Offer, PackageSize
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def repository():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = SQLAlchemyOfferRepositoryAdapter(session)
    yield repo
    session.close()


def _build_offer(*, post_id=None, user_id=None, offer_id=None) -> Offer:
    return Offer(
        id=offer_id or uuid4(),
        post_id=post_id or uuid4(),
        user_id=user_id or uuid4(),
        description="Entrega urgente",
        size=PackageSize.MEDIUM,
        fragile=False,
        offer=Decimal("150.50"),
        created_at=datetime.now(timezone.utc),
    )


def test_create_and_get_by_id(repository):
    offer = _build_offer()

    created = repository.create(offer)

    assert created.id == offer.id
    assert created.post_id == offer.post_id
    assert repository.get_by_id(offer.id) == created


def test_search_filters_by_post_and_user(repository):
    post_one = uuid4()
    user_one = uuid4()
    post_two = uuid4()
    user_two = uuid4()

    repository.create(
        _build_offer(post_id=post_one, user_id=user_one, offer_id=uuid4())
    )
    repository.create(
        _build_offer(post_id=post_one, user_id=user_two, offer_id=uuid4())
    )
    repository.create(
        _build_offer(post_id=post_two, user_id=user_one, offer_id=uuid4())
    )

    by_post = repository.search(post_id=post_one)
    by_user = repository.search(user_id=user_one)
    by_both = repository.search(post_id=post_one, user_id=user_one)

    assert len(by_post) == 2
    assert len(by_user) == 2
    assert len(by_both) == 1
    assert all(item.post_id == post_one for item in by_post)
    assert all(item.user_id == user_one for item in by_user)
    assert by_both[0].post_id == post_one
    assert by_both[0].user_id == user_one


def test_delete_count_and_delete_all(repository):
    first = repository.create(_build_offer())
    second = repository.create(_build_offer())

    assert repository.count() == 2
    assert repository.delete(first.id) is True
    assert repository.count() == 1
    assert repository.get_by_id(first.id) is None
    assert repository.delete(second.id) is True
    assert repository.count() == 0

    repository.create(_build_offer())
    deleted_items = repository.delete_all()
    assert deleted_items == 1
    assert repository.count() == 0


def test_create_duplicate_id_raises(repository):
    offer = _build_offer()
    repository.create(offer)

    with pytest.raises(IntegrityError):
        repository.create(_build_offer(offer_id=offer.id))


def test_non_unique_integrity_errors_surface(repository):
    offer = _build_offer()
    offer.description = None

    with pytest.raises(IntegrityError):
        repository.create(offer)
