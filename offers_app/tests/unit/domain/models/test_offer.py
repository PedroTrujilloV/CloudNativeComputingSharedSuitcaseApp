from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from domain.models.offer import (
    Offer,
    OfferCreateRequest,
    OfferCreateResponse,
    PackageSize,
)
from pydantic import ValidationError


def test_offer_model_stores_values():
    offer_id = uuid4()
    post_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    offer = Offer(
        id=offer_id,
        post_id=post_id,
        user_id=user_id,
        description="Entrega urgente",
        size=PackageSize.LARGE,
        fragile=True,
        offer=Decimal("250.00"),
        created_at=now,
    )

    assert offer.id == offer_id
    assert offer.post_id == post_id
    assert offer.user_id == user_id
    assert offer.description == "Entrega urgente"
    assert offer.size == PackageSize.LARGE
    assert offer.fragile is True
    assert offer.offer == Decimal("250.00")
    assert offer.created_at == now


def test_package_size_values_are_valid_enum_members():
    assert PackageSize.SMALL.value == "SMALL"
    assert PackageSize.MEDIUM.value == "MEDIUM"
    assert PackageSize.LARGE.value == "LARGE"

    assert list(PackageSize) == [
        PackageSize.LARGE,
        PackageSize.MEDIUM,
        PackageSize.SMALL,
    ]


def test_offer_equality_uses_all_fields():
    now = datetime.now(timezone.utc)
    offer_a = Offer(
        id=uuid4(),
        post_id=uuid4(),
        user_id=uuid4(),
        description="Entrega",
        size=PackageSize.MEDIUM,
        fragile=False,
        offer=Decimal("100.00"),
        created_at=now,
    )
    offer_b = Offer(
        id=offer_a.id,
        post_id=offer_a.post_id,
        user_id=offer_a.user_id,
        description=offer_a.description,
        size=offer_a.size,
        fragile=offer_a.fragile,
        offer=offer_a.offer,
        created_at=offer_a.created_at,
    )

    assert offer_a == offer_b


def test_offer_create_request_rejects_empty_description():
    with pytest.raises(ValidationError):
        OfferCreateRequest(
            post_id=uuid4(),
            user_id=uuid4(),
            description="",
            size=PackageSize.SMALL,
            fragile=False,
            offer=Decimal("10.00"),
        )


def test_offer_create_response_exposes_expected_fields():
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    response = OfferCreateResponse(
        id=uuid4(),
        user_id=user_id,
        created_at=now,
    )

    assert response.user_id == user_id
    assert response.created_at == now


def test_offer_is_a_pydantic_model():
    now = datetime.now(timezone.utc)
    offer = Offer(
        id=uuid4(),
        post_id=uuid4(),
        user_id=uuid4(),
        description="Entrega",
        size=PackageSize.SMALL,
        fragile=False,
        offer=Decimal("150.50"),
        created_at=now,
    )

    assert offer.model_dump()["description"] == "Entrega"
    assert Offer.model_fields["offer"].annotation is Decimal
