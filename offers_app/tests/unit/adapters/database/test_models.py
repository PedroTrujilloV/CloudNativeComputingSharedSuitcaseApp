from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from adapters.database.models import Base, OfferModel
from domain.models.offer import PackageSize
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_offer_model_defines_expected_table_and_columns():
    columns = OfferModel.__table__.columns.keys()

    assert OfferModel.__tablename__ == "offers"
    assert list(columns) == [
        "id",
        "postId",
        "userId",
        "description",
        "size",
        "fragile",
        "offer",
        "createdAt",
    ]


def test_offer_model_round_trips_through_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    offer_id = uuid4()
    post_id = uuid4()
    user_id = uuid4()
    created_at = datetime.now(timezone.utc)

    model = OfferModel(
        id=offer_id,
        postId=post_id,
        userId=user_id,
        description="Entrega urgente",
        size=PackageSize.SMALL,
        fragile=True,
        offer=Decimal("199.99"),
        createdAt=created_at,
    )

    session.add(model)
    session.commit()

    stored_model = session.get(OfferModel, offer_id)

    assert stored_model is not None
    assert OfferModel.__table__.c.createdAt.type.timezone is True
    assert stored_model.id == offer_id
    assert stored_model.postId == post_id
    assert stored_model.userId == user_id
    assert stored_model.description == "Entrega urgente"
    assert stored_model.size == PackageSize.SMALL
    assert stored_model.fragile is True
    assert stored_model.offer == Decimal("199.99")
    stored_created_at = stored_model.createdAt
    if stored_created_at.tzinfo is None:
        stored_created_at = stored_created_at.replace(tzinfo=timezone.utc)
    assert stored_created_at == created_at

    session.close()
