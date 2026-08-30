from uuid import uuid4


def _valid_payload(**overrides):
    payload = {
        "postId": str(uuid4()),
        "userId": str(uuid4()),
        "description": "Entrega urgente",
        "size": "MEDIUM",
        "fragile": False,
        "offer": "150.50",
    }
    payload.update(overrides)
    return payload


def test_ping_returns_pong(client):
    """GET /offers/ping should return 200 with body pong."""
    response = client.get("/offers/ping")

    assert response.status_code == 200
    assert response.text == "pong"


def test_create_offer_returns_201_with_camel_case_body(client):
    """POST /offers should return 201 with id, userId and createdAt."""
    response = client.post("/offers", json=_valid_payload())

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"id", "userId", "createdAt"}
    assert body["id"]


def test_create_offer_description_too_long_returns_412(client):
    """A description longer than 140 characters is a domain error."""
    response = client.post(
        "/offers", json=_valid_payload(description="x" * 141)
    )

    assert response.status_code == 412


def test_create_offer_too_many_decimals_returns_412(client):
    """An offer with more than two decimal places is a domain error."""
    response = client.post("/offers", json=_valid_payload(offer="150.505"))

    assert response.status_code == 412


def test_create_offer_negative_value_returns_412(client):
    """A negative offer value should return 412."""
    response = client.post("/offers", json=_valid_payload(offer="-10.00"))

    assert response.status_code == 412


def test_create_offer_invalid_size_returns_412(client):
    """An invalid package size should return 412."""
    response = client.post(
        "/offers",
        json=_valid_payload(size="HUGE"),
    )

    assert response.status_code == 412


def test_create_offer_rejects_invalid_payload(client):
    """POST /offers with missing/malformed fields returns 400; domain errors return 412."""
    missing_field_payloads = [
        {},
        {"postId": "not-a-uuid"},
        {"postId": str(uuid4()), "userId": str(uuid4())},
    ]
    for payload in missing_field_payloads:
        response = client.post("/offers", json=payload)
        assert response.status_code == 400

    # Invalid size is a domain error, not a format error
    response = client.post(
        "/offers",
        json=_valid_payload(size="HUGE"),
    )
    assert response.status_code == 412


def test_reset_returns_success_message(client):
    """POST /offers/reset should return the expected JSON message."""
    response = client.post("/offers/reset")

    assert response.status_code == 200
    assert response.json() == {"msg": "Todos los datos fueron eliminados"}


def test_reset_deletes_all_offers(client):
    """POST /offers/reset should remove every stored offer."""
    payload = _valid_payload()
    assert client.post("/offers", json=payload).status_code == 201

    reset = client.post("/offers/reset")
    assert reset.status_code == 200

    # The same postId+userId is accepted again after the reset.
    assert client.post("/offers", json=payload).status_code == 201


def test_list_offers_empty_by_default(client):
    """GET /offers with no data should return an empty array."""
    response = client.get("/offers")

    assert response.status_code == 200
    assert response.json() == []


def test_list_offers_no_params_returns_full_list(client):
    """GET /offers with no params returns all offers unfiltered."""
    client.post("/offers", json=_valid_payload())
    client.post("/offers", json=_valid_payload())

    response = client.get("/offers")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_offers_filters_by_post(client):
    """GET /offers?post= should only return matching offers."""
    target_post = str(uuid4())
    client.post("/offers", json=_valid_payload(postId=target_post))
    client.post("/offers", json=_valid_payload())

    response = client.get("/offers", params={"post": target_post})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["postId"] == target_post


def test_list_offers_filters_by_owner(client):
    """GET /offers?owner= should only return matching offers."""
    target_user = str(uuid4())
    client.post("/offers", json=_valid_payload(userId=target_user))
    client.post("/offers", json=_valid_payload())

    response = client.get("/offers", params={"owner": target_user})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["userId"] == target_user


def test_list_offers_applies_and_semantics(client):
    """Combining post and owner filters uses AND semantics."""
    target_post = str(uuid4())
    target_user = str(uuid4())
    # Matches both filters.
    client.post(
        "/offers", json=_valid_payload(postId=target_post, userId=target_user)
    )
    # Matches post only.
    client.post("/offers", json=_valid_payload(postId=target_post))
    # Matches owner only.
    client.post("/offers", json=_valid_payload(userId=target_user))
    client.post("/offers", json=_valid_payload())

    response = client.get(
        "/offers", params={"post": target_post, "owner": target_user}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["postId"] == target_post
    assert body[0]["userId"] == target_user


def test_list_offers_returns_full_offer_object(client):
    """GET /offers returns the full camelCase Oferta object."""
    payload = _valid_payload()
    client.post("/offers", json=payload)

    response = client.get("/offers")

    assert response.status_code == 200
    body = response.json()[0]
    assert set(body.keys()) == {
        "id",
        "postId",
        "userId",
        "description",
        "size",
        "fragile",
        "offer",
        "createdAt",
    }


def test_list_offers_malformed_post_returns_400(client):
    """A malformed post filter value should return 400."""
    response = client.get("/offers", params={"post": "not-a-uuid"})

    assert response.status_code == 400


def test_list_offers_malformed_owner_returns_400(client):
    """A malformed owner filter value should return 400."""
    response = client.get("/offers", params={"owner": "not-a-uuid"})

    assert response.status_code == 400


def test_get_offer_returns_200_with_full_object(client):
    """GET /offers/{id} returns the full offer for an existing id."""
    create = client.post("/offers", json=_valid_payload())
    offer_id = create.json()["id"]

    response = client.get(f"/offers/{offer_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == offer_id
    assert set(body.keys()) == {
        "id",
        "postId",
        "userId",
        "description",
        "size",
        "fragile",
        "offer",
        "createdAt",
    }


def test_get_offer_invalid_uuid_returns_400(client):
    """GET /offers/{id} with a malformed id should return 400."""
    response = client.get("/offers/not-a-uuid")

    assert response.status_code == 400


def test_get_offer_not_found_returns_404(client):
    """GET /offers/{id} with a valid but unknown id should return 404."""
    response = client.get(f"/offers/{uuid4()}")

    assert response.status_code == 404


def test_delete_offer_returns_200_and_removes(client):
    """DELETE /offers/{id} removes the offer and returns the expected message."""
    create = client.post("/offers", json=_valid_payload())
    offer_id = create.json()["id"]

    response = client.delete(f"/offers/{offer_id}")

    assert response.status_code == 200
    assert response.json() == {"msg": "la oferta fue eliminada"}

    assert client.get(f"/offers/{offer_id}").status_code == 404


def test_delete_offer_invalid_uuid_returns_400(client):
    """DELETE /offers/{id} with a malformed id should return 400."""
    response = client.delete("/offers/not-a-uuid")

    assert response.status_code == 400


def test_delete_offer_not_found_returns_404(client):
    """DELETE /offers/{id} with a valid but unknown id should return 404."""
    response = client.delete(f"/offers/{uuid4()}")

    assert response.status_code == 404


def test_count_returns_zero_when_empty(client):
    """GET /offers/count should return zero when no offers exist."""
    response = client.get("/offers/count")

    assert response.status_code == 200
    assert response.json() == {"count": 0}


def test_count_reflects_stored_offers(client):
    """GET /offers/count reflects the number of stored offers."""
    client.post("/offers", json=_valid_payload())
    client.post("/offers", json=_valid_payload())

    response = client.get("/offers/count")

    assert response.status_code == 200
    assert response.json() == {"count": 2}