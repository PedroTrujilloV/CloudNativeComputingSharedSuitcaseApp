"""Unit tests for the Posts service HTTP client."""

import json
from datetime import datetime, timezone

import httpx
import pytest

from adapters.http.posts_service_client import PostsServiceClient
from errors import ExpireAtInvalidError, PostsServiceUnavailableError

BASE = "http://posts.test"


def _client(handler) -> PostsServiceClient:
    transport = httpx.MockTransport(handler)
    return PostsServiceClient(client=httpx.Client(base_url=BASE, transport=transport))


def test_has_post_returns_true_when_owner_has_a_post():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["route"] == "route-1"
        assert request.url.params["owner"] == "user-1"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "post-1",
                    "routeId": "route-1",
                    "userId": "user-1",
                    "expireAt": "2026-09-15T10:00:00Z",
                    "createdAt": "2026-09-01T10:00:00Z",
                }
            ],
        )

    client = _client(handler)
    assert client.has_post_for_route_and_owner("route-1", "user-1") is True


def test_has_post_returns_false_when_no_post():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _client(handler)
    assert client.has_post_for_route_and_owner("route-1", "user-1") is False


def test_has_post_unreachable_raises_503_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    with pytest.raises(PostsServiceUnavailableError):
        client.has_post_for_route_and_owner("route-1", "user-1")


def test_has_post_non_200_raises_503_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    client = _client(handler)
    with pytest.raises(PostsServiceUnavailableError):
        client.has_post_for_route_and_owner("route-1", "user-1")


def test_create_post_sends_camel_case_body_and_returns_view():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "id": "post-9",
                "userId": "user-1",
                "createdAt": "2026-09-02T08:00:00Z",
            },
        )

    client = _client(handler)
    created = client.create_post(
        route_id="route-1", user_id="user-1", expire_at=datetime(2026, 9, 15, 10, 0)
    )

    assert created.id == "post-9"
    assert created.userId == "user-1"
    assert created.createdAt == datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc)
    assert seen["body"] == {
        "routeId": "route-1",
        "userId": "user-1",
        "expireAt": "2026-09-15T10:00:00",
    }


def test_create_post_412_raises_expire_at_invalid():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(412, json={"msg": "La fecha expiración no es válida"})

    client = _client(handler)
    with pytest.raises(ExpireAtInvalidError):
        client.create_post(
            route_id="route-1",
            user_id="user-1",
            expire_at=datetime(2020, 1, 1),
        )


def test_create_post_unreachable_raises_503_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    with pytest.raises(PostsServiceUnavailableError):
        client.create_post(
            route_id="route-1", user_id="user-1", expire_at=datetime(2026, 9, 15)
        )


def test_create_post_unexpected_status_raises_503_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"msg": "routeId y userId deben ser UUID válidos"}
        )

    client = _client(handler)
    with pytest.raises(PostsServiceUnavailableError):
        client.create_post(
            route_id="not-a-uuid", user_id="user-1", expire_at=datetime(2026, 9, 15)
        )
