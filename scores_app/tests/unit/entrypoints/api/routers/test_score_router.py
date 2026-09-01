from uuid import uuid4

from fastapi.testclient import TestClient


def _valid_payload(**overrides):
    payload = {"offerId": str(uuid4()), "score": 150.5}
    payload.update(overrides)
    return payload


def test_ping_returns_200_pong(client: TestClient):
    """The health-check endpoint should return 200 with a plain-text body."""
    response = client.get("/scores/ping")

    assert response.status_code == 200
    assert response.text == "pong"
    assert response.headers["content-type"].startswith("text/plain")


def test_post_score_creates_returns_201_with_expected_fields(client):
    """POST /scores on a new offer returns 201 with id, offerId, score, createdAt."""
    payload = _valid_payload()

    response = client.post("/scores", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"id", "offerId", "score", "createdAt"}
    assert body["offerId"] == payload["offerId"]
    assert body["score"] == payload["score"]
    assert body["id"]


def test_post_score_updates_existing_returns_200_with_updated_at(client):
    """POST /scores on an existing offer returns 200 with updatedAt, not createdAt."""
    payload = _valid_payload()

    created = client.post("/scores", json=payload)
    assert created.status_code == 201

    update = client.post(
        "/scores", json=_valid_payload(offerId=payload["offerId"], score=999.25)
    )
    assert update.status_code == 200
    body = update.json()
    assert set(body.keys()) == {"id", "offerId", "score", "updatedAt"}
    assert body["id"] == created.json()["id"]
    assert body["score"] == 999.25


def test_post_score_missing_fields_returns_400(client):
    """Missing offerId or score is a validation error mapped to 400 (no body)."""
    for payload in [{}, {"offerId": str(uuid4())}, {"score": 10.0}]:
        response = client.post("/scores", json=payload)
        assert response.status_code == 400
        assert response.text == ""


def test_post_score_malformed_offer_id_returns_400(client):
    """A non-UUID offerId is rejected with 400."""
    response = client.post("/scores", json=_valid_payload(offerId="not-a-uuid"))

    assert response.status_code == 400
    assert response.text == ""


def test_post_score_malformed_score_returns_400(client):
    """A non-numeric score is rejected with 400."""
    response = client.post("/scores", json=_valid_payload(score="abc"))

    assert response.status_code == 400
    assert response.text == ""


def test_get_score_by_offer_returns_200_with_score_when_it_exists(client):
    """GET /scores?offerId returns 200 with id, offerId, score, createdAt."""
    payload = _valid_payload()
    created = client.post("/scores", json=payload)
    assert created.status_code == 201

    response = client.get("/scores", params={"offerId": payload["offerId"]})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"id", "offerId", "score", "createdAt"}
    assert body["id"] == created.json()["id"]
    assert body["score"] == payload["score"]


def test_get_score_by_offer_missing_is_null_safe_200(client):
    """GET /scores?offerId with no score returns 200 with score: null (not 404)."""
    response = client.get("/scores", params={"offerId": str(uuid4())})

    assert response.status_code == 200
    assert response.json() == {"offerId": response.json()["offerId"], "score": None}
    assert set(response.json().keys()) == {"offerId", "score"}


def test_get_score_by_offer_missing_param_returns_400(client):
    """GET /scores without offerId returns 400 (no body)."""
    response = client.get("/scores")

    assert response.status_code == 400
    assert response.text == ""


def test_get_score_by_offer_malformed_uuid_returns_400(client):
    """GET /scores?offerId with a non-UUID value returns 400 (no body)."""
    response = client.get("/scores", params={"offerId": "not-a-uuid"})

    assert response.status_code == 400
    assert response.text == ""


def test_get_score_by_id_returns_200_with_all_fields(client):
    """GET /scores/{id} returns 200 with id, offerId, score, createdAt, updatedAt."""
    created = client.post("/scores", json=_valid_payload())
    assert created.status_code == 201
    score_id = created.json()["id"]

    response = client.get(f"/scores/{score_id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "id",
        "offerId",
        "score",
        "createdAt",
        "updatedAt",
    }
    assert body["id"] == score_id


def test_get_score_by_id_malformed_uuid_returns_400(client):
    """GET /scores/{id} with a non-UUID id returns 400 (no body)."""
    response = client.get("/scores/not-a-uuid")

    assert response.status_code == 400
    assert response.text == ""


def test_get_score_by_id_not_found_returns_404(client):
    """GET /scores/{id} for an unknown UUID returns 404 (no body)."""
    response = client.get(f"/scores/{uuid4()}")

    assert response.status_code == 404
    assert response.text == ""


def test_count_returns_zero_when_empty(client):
    """GET /scores/count returns 200 with count 0 on an empty store."""
    response = client.get("/scores/count")

    assert response.status_code == 200
    assert response.json() == {"count": 0}


def test_count_reflects_persisted_scores(client):
    """GET /scores/count counts one row per offer (updates do not add rows)."""
    client.post("/scores", json=_valid_payload())
    client.post("/scores", json=_valid_payload())
    client.post("/scores", json=_valid_payload())

    response = client.get("/scores/count")

    assert response.status_code == 200
    assert response.json() == {"count": 3}


def test_reset_returns_expected_message(client):
    """POST /scores/reset returns 200 with the English success message."""
    response = client.post("/scores/reset")

    assert response.status_code == 200
    assert response.json() == {"msg": "All data was deleted"}


def test_reset_deletes_all_scores(client):
    """POST /scores/reset removes every stored score."""
    payload = _valid_payload()
    assert client.post("/scores", json=payload).status_code == 201

    assert client.post("/scores/reset").status_code == 200

    # The offer is back to the null-safe state after the reset.
    response = client.get("/scores", params={"offerId": payload["offerId"]})
    assert response.status_code == 200
    assert response.json()["score"] is None
    assert client.get("/scores/count").json() == {"count": 0}
