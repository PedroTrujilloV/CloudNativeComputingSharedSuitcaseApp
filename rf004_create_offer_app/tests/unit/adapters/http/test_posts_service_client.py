"""Unit tests for the Posts service HTTP client (post lookup)."""

from datetime import datetime, timezone

import httpx
import pytest

from adapters.http.posts_service_client import PostsServiceClient
from errors import PostNotFoundError, PostsServiceUnavailableError

BASE = "http://posts.test"


def _client(handler) -> PostsServiceClient:
    transport = httpx.MockTransport(handler)
    return PostsServiceClient(client=httpx.Client(base_url=BASE, transport=transport))


def test_get_post_success_returns_post_info():
    """A 200 from GET /posts/{id} maps to a PostInfo view."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/posts/post-1"
        return httpx.Response(
            200,
            json={
                "id": "post-1",
                "routeId": "route-1",
                "userId": "owner-1",
                "expireAt": "2026-09-15T10:00:00Z",
                "createdAt": "2026-09-01T10:00:00Z",
            },
        )

    client = _client(handler)
    post = client.get_post("post-1")

    assert post.id == "post-1"
    assert post.routeId == "route-1"
    assert post.userId == "owner-1"
    assert post.expireAt == datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)


def test_get_post_success_with_naive_expire_at():
    """An expireAt without a ``Z`` suffix is also parsed (naive, assumed UTC)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "post-1",
                "routeId": "route-1",
                "userId": "owner-1",
                "expireAt": "2026-09-15T10:00:00",
                "createdAt": "2026-09-01T10:00:00",
            },
        )

    client = _client(handler)
    post = client.get_post("post-1")

    assert post.expireAt == datetime(2026, 9, 15, 10, 0)


def test_get_post_404_raises_not_found():
    """A 404 from the Posts service maps to PostNotFoundError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"msg": "No existe una publicación"})

    client = _client(handler)
    with pytest.raises(PostNotFoundError):
        client.get_post("missing")


def test_get_post_400_non_uuid_raises_not_found():
    """A 400 (non-UUID id) from the Posts service maps to PostNotFoundError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"msg": "El id debe ser un UUID válido"})

    client = _client(handler)
    with pytest.raises(PostNotFoundError):
        client.get_post("not-a-uuid")


def test_get_post_503_raises_unavailable():
    """A 5xx from the Posts service maps to PostsServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    client = _client(handler)
    with pytest.raises(PostsServiceUnavailableError):
        client.get_post("post-1")


def test_get_post_network_error_raises_unavailable():
    """A connection error maps to PostsServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    with pytest.raises(PostsServiceUnavailableError):
        client.get_post("post-1")
