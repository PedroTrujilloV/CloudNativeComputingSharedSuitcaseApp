"""
Unit tests for the Posts listing, lookup, deletion, count and reset endpoints.
Covers issue #26.
"""
from datetime import datetime, timedelta


ROUTE_A = "11111111-1111-4111-8111-111111111111"
ROUTE_B = "22222222-2222-4222-8222-222222222222"
OWNER_A = "33333333-3333-4333-8333-333333333333"
OWNER_B = "44444444-4444-4444-8444-444444444444"

UNKNOWN_ID = "99999999-9999-4999-8999-999999999999"


def create_post(client, route_id=ROUTE_A, user_id=OWNER_A, hours=5):
    """Create a publication through the API and return its id."""
    response = client.post(
        "/posts",
        json={
            "routeId": route_id,
            "userId": user_id,
            "expireAt": (datetime.utcnow() + timedelta(hours=hours)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def insert_expired_post(route_id=ROUTE_A, user_id=OWNER_A):
    """Insert an already-expired publication straight through the repository.

    The API rejects a past expireAt with 412, so the expire filter cannot be
    exercised through POST /posts alone.
    """
    from adapters.database.models import Publication
    from adapters.database.repository import PublicationRepository

    repository = PublicationRepository()
    session = repository.SessionLocal()
    try:
        publication = Publication(
            route_id=route_id,
            user_id=user_id,
            expire_at=datetime.utcnow() - timedelta(hours=1),
        )
        session.add(publication)
        session.commit()
        return publication.id
    finally:
        session.close()


class TestListPosts:
    """GET /posts"""

    def test_list_returns_empty_array_when_no_posts(self, client):
        response = client.get("/posts")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_without_filters_returns_every_post(self, client):
        create_post(client, route_id=ROUTE_A)
        create_post(client, route_id=ROUTE_B)

        response = client.get("/posts")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_returns_full_publication_object(self, client):
        post_id = create_post(client)

        body = client.get("/posts").json()[0]

        assert body["id"] == post_id
        assert body["routeId"] == ROUTE_A
        assert body["userId"] == OWNER_A
        assert "expireAt" in body
        assert "createdAt" in body

    def test_list_filters_by_route(self, client):
        create_post(client, route_id=ROUTE_A)
        create_post(client, route_id=ROUTE_B)

        body = client.get(f"/posts?route={ROUTE_A}").json()

        assert len(body) == 1
        assert body[0]["routeId"] == ROUTE_A

    def test_list_filters_by_owner(self, client):
        create_post(client, user_id=OWNER_A)
        create_post(client, user_id=OWNER_B)

        body = client.get(f"/posts?owner={OWNER_A}").json()

        assert len(body) == 1
        assert body[0]["userId"] == OWNER_A

    def test_list_filters_by_expire_false_returns_active_posts(self, client):
        create_post(client)
        insert_expired_post()

        body = client.get("/posts?expire=false").json()

        assert len(body) == 1

    def test_list_filters_by_expire_true_returns_expired_posts(self, client):
        create_post(client)
        expired_id = insert_expired_post()

        body = client.get("/posts?expire=true").json()

        assert len(body) == 1
        assert body[0]["id"] == expired_id

    def test_list_combines_filters_with_and_semantics(self, client):
        create_post(client, route_id=ROUTE_A, user_id=OWNER_A)
        create_post(client, route_id=ROUTE_A, user_id=OWNER_B)
        create_post(client, route_id=ROUTE_B, user_id=OWNER_A)

        body = client.get(f"/posts?route={ROUTE_A}&owner={OWNER_A}").json()

        assert len(body) == 1
        assert body[0]["routeId"] == ROUTE_A
        assert body[0]["userId"] == OWNER_A

    def test_list_combines_expire_and_route(self, client):
        expired_on_a = insert_expired_post(route_id=ROUTE_A)
        create_post(client, route_id=ROUTE_A)
        insert_expired_post(route_id=ROUTE_B)

        body = client.get(f"/posts?expire=true&route={ROUTE_A}").json()

        assert len(body) == 1
        assert body[0]["id"] == expired_on_a

    def test_list_combines_expire_and_owner(self, client):
        expired_of_a = insert_expired_post(user_id=OWNER_A)
        create_post(client, user_id=OWNER_A)
        insert_expired_post(user_id=OWNER_B)

        body = client.get(f"/posts?expire=true&owner={OWNER_A}").json()

        assert len(body) == 1
        assert body[0]["id"] == expired_of_a

    def test_list_combines_all_three_filters(self, client):
        target = insert_expired_post(route_id=ROUTE_A, user_id=OWNER_A)
        insert_expired_post(route_id=ROUTE_A, user_id=OWNER_B)
        insert_expired_post(route_id=ROUTE_B, user_id=OWNER_A)
        create_post(client, route_id=ROUTE_A, user_id=OWNER_A)

        body = client.get(f"/posts?expire=true&route={ROUTE_A}&owner={OWNER_A}").json()

        assert len(body) == 1
        assert body[0]["id"] == target

    def test_list_returns_empty_array_when_filter_matches_nothing(self, client):
        create_post(client, route_id=ROUTE_A)

        body = client.get(f"/posts?route={ROUTE_B}").json()

        assert body == []

    def test_list_malformed_expire_returns_400(self, client):
        assert client.get("/posts?expire=maybe").status_code == 400

    def test_list_malformed_route_returns_400(self, client):
        assert client.get("/posts?route=not-a-uuid").status_code == 400

    def test_list_malformed_owner_returns_400(self, client):
        assert client.get("/posts?owner=123").status_code == 400


class TestGetPostById:
    """GET /posts/{id}"""

    def test_get_by_id_returns_200_with_publication(self, client):
        post_id = create_post(client)

        response = client.get(f"/posts/{post_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == post_id
        assert body["routeId"] == ROUTE_A
        assert body["userId"] == OWNER_A

    def test_get_by_id_invalid_uuid_returns_400(self, client):
        assert client.get("/posts/not-a-uuid").status_code == 400

    def test_get_by_id_unknown_id_returns_404(self, client):
        assert client.get(f"/posts/{UNKNOWN_ID}").status_code == 404


class TestDeletePost:
    """DELETE /posts/{id}"""

    def test_delete_returns_200_with_confirmation_message(self, client):
        post_id = create_post(client)

        response = client.delete(f"/posts/{post_id}")

        assert response.status_code == 200
        assert response.json() == {"msg": "la publicación fue eliminada"}

    def test_delete_removes_the_publication(self, client):
        post_id = create_post(client)

        client.delete(f"/posts/{post_id}")

        assert client.get(f"/posts/{post_id}").status_code == 404

    def test_delete_invalid_uuid_returns_400(self, client):
        assert client.delete("/posts/not-a-uuid").status_code == 400

    def test_delete_unknown_id_returns_404(self, client):
        assert client.delete(f"/posts/{UNKNOWN_ID}").status_code == 404


class TestCountPosts:
    """GET /posts/count"""

    def test_count_is_zero_when_empty(self, client):
        response = client.get("/posts/count")

        assert response.status_code == 200
        assert response.json() == {"count": 0}

    def test_count_reflects_created_posts(self, client):
        create_post(client)
        create_post(client)

        assert client.get("/posts/count").json() == {"count": 2}

    def test_count_is_not_shadowed_by_the_id_route(self, client):
        """/posts/count must not be captured by GET /posts/{id}."""
        assert client.get("/posts/count").status_code == 200


class TestResetPosts:
    """POST /posts/reset"""

    def test_reset_returns_confirmation_message(self, client):
        response = client.post("/posts/reset")

        assert response.status_code == 200
        assert response.json() == {"msg": "Todos los datos fueron eliminados"}

    def test_reset_deletes_every_publication(self, client):
        create_post(client)
        create_post(client)

        client.post("/posts/reset")

        assert client.get("/posts/count").json() == {"count": 0}
        assert client.get("/posts").json() == []
