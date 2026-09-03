"""Unit tests for the Users service client adapter."""

import httpx
import pytest

from adapters.http.users_service_client import UsersServiceClient
from errors import (
    InvalidTokenError,
    TokenMissingError,
    UsersServiceUnavailableError,
)


def _client(handler) -> UsersServiceClient:
    transport = httpx.MockTransport(handler)
    return UsersServiceClient(
        client=httpx.Client(base_url="http://users.test", transport=transport)
    )


def test_validate_token_success_returns_authenticated_user():
    """A 200 from /users/me maps to an AuthenticatedUser."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/me"
        assert request.headers["Authorization"] == "Bearer valid-token"
        return httpx.Response(200, json={"id": "user-1", "username": "tester"})

    client = _client(handler)
    user = client.validate_token("valid-token")

    assert user.id == "user-1"
    assert user.username == "tester"


def test_validate_token_missing_token_raises_token_missing():
    """An empty token raises TokenMissingError without any HTTP call."""
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    client = _client(handler)
    with pytest.raises(TokenMissingError):
        client.validate_token("")
    assert called is False


def test_validate_token_401_raises_invalid_token():
    """A 401 from the Users service maps to InvalidTokenError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    client = _client(handler)
    with pytest.raises(InvalidTokenError):
        client.validate_token("bad-token")


def test_validate_token_500_raises_unavailable():
    """A 5xx from the Users service maps to UsersServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client(handler)
    with pytest.raises(UsersServiceUnavailableError):
        client.validate_token("valid-token")


def test_validate_token_network_error_raises_unavailable():
    """A connection error maps to UsersServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client(handler)
    with pytest.raises(UsersServiceUnavailableError):
        client.validate_token("valid-token")
