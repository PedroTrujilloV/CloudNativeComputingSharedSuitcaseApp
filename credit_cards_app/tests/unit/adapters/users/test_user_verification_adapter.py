import json

import httpx2
import pytest

from adapters.users.user_verification_adapter import (
    UsersAppUserVerificationAdapter,
)
from errors import InvalidTokenError, UserVerificationUnavailableError

BASE_URL = "http://users-app.test"


def build_adapter(handler) -> UsersAppUserVerificationAdapter:
    transport = httpx2.MockTransport(handler)
    return UsersAppUserVerificationAdapter(
        base_url=BASE_URL,
        client_factory=lambda: httpx2.Client(transport=transport),
    )


def handler_returning(status_code: int, body: dict):
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "GET"
        assert request.url.path == "/users/me"
        return httpx2.Response(status_code, json=body, request=request)

    return handler


def test_a_valid_token_returns_the_owner_user_id_and_email():
    adapter = build_adapter(
        handler_returning(
            200, {"id": "user-1", "username": "jane", "email": "jane@example.com"}
        )
    )

    verified = adapter.verify("the-token")

    assert verified.id == "user-1"
    assert verified.email == "jane@example.com"


def test_a_valid_token_without_an_email_returns_an_empty_email():
    adapter = build_adapter(handler_returning(200, {"id": "user-1"}))

    verified = adapter.verify("the-token")

    assert verified.id == "user-1"
    assert verified.email == ""


def test_the_bearer_header_is_forwarded_to_the_users_application():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["authorization"] = request.headers.get("authorization")
        return httpx2.Response(200, json={"id": "user-1"}, request=request)

    adapter = build_adapter(handler)
    verified = adapter.verify("secret-token")

    assert seen["authorization"] == "Bearer secret-token"
    assert verified.id == "user-1"


def test_an_invalid_token_raises_invalid_token_error():
    adapter = build_adapter(handler_returning(401, {}))

    with pytest.raises(InvalidTokenError):
        adapter.verify("expired-token")


def test_a_403_from_the_users_application_raises_invalid_token_error():
    adapter = build_adapter(handler_returning(403, {}))

    with pytest.raises(InvalidTokenError):
        adapter.verify("denied-token")


def test_an_unexpected_status_raises_unavailable():
    adapter = build_adapter(handler_returning(500, {}))

    with pytest.raises(UserVerificationUnavailableError):
        adapter.verify("the-token")


def test_an_answer_without_an_id_raises_unavailable():
    adapter = build_adapter(handler_returning(200, {"username": "jane"}))

    with pytest.raises(UserVerificationUnavailableError):
        adapter.verify("the-token")


def test_an_unparseable_answer_raises_unavailable():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200, content=b"not json", request=request, headers={"Content-Type": "text/plain"}
        )

    adapter = build_adapter(handler)

    with pytest.raises(UserVerificationUnavailableError):
        adapter.verify("the-token")


def test_a_non_dict_answer_raises_unavailable():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200, content=json.dumps(["id"]), request=request
        )

    adapter = build_adapter(handler)

    with pytest.raises(UserVerificationUnavailableError):
        adapter.verify("the-token")


def test_a_network_failure_raises_unavailable():
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused")

    adapter = build_adapter(handler)

    with pytest.raises(UserVerificationUnavailableError):
        adapter.verify("the-token")
