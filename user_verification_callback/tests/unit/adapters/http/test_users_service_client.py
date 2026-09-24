"""Unit tests for the Users service client adapter."""

import json

import httpx
import pytest

from adapters.http.users_service_client import UsersServiceClient
from domain.models.updated_user_data import UpdatedUserData
from errors import UserNotFoundError, UsersServiceUnavailableError


def _client(handler) -> UsersServiceClient:
    transport = httpx.MockTransport(handler)
    return UsersServiceClient(
        client=httpx.Client(base_url="http://users.test", transport=transport)
    )


def test_update_status_success_sends_patch_with_status_body():
    """A 200 from the Users service is accepted and the PATCH is well formed."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/users/user-1"
        assert json.loads(request.content) == {"status": "VERIFICADO"}
        return httpx.Response(
            200,
            json={
                "msg": "User updated",
                "user": {
                    "id": "user-1",
                    "username": "user_1",
                    "email": "user_1@example.com",
                    "dni": "12345678",
                    "fullName": "User One",
                    "phoneNumber": "3001234567",
                    "status": "VERIFICADO",
                    "ruv": "ruv-1",
                    "updatedAt": "2026-09-23T12:00:00Z",
                },
            },
        )

    client = _client(handler)

    data = client.update_status("user-1", "VERIFICADO")

    assert data == UpdatedUserData(
        id="user-1",
        username="user_1",
        email="user_1@example.com",
        dni="12345678",
        fullName="User One",
        phoneNumber="3001234567",
        status="VERIFICADO",
        ruv="ruv-1",
        updatedAt="2026-09-23T12:00:00Z",
    )


def test_update_status_parses_partial_user_block():
    """Absent optional user fields stay None in the returned data."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"msg": "ok", "user": {"id": "user-1", "status": "NO_VERIFICADO"}},
        )

    client = _client(handler)

    data = client.update_status("user-1", "NO_VERIFICADO")

    assert data.id == "user-1"
    assert data.status == "NO_VERIFICADO"
    assert data.username is None
    assert data.ruv is None


def test_update_status_ignores_unknown_user_fields():
    """Extra keys in the user block are dropped, known ones are kept."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "msg": "ok",
                "user": {
                    "id": "user-1",
                    "status": "VERIFICADO",
                    "password": "must-not-leak",
                    "salt": "must-not-leak",
                },
            },
        )

    client = _client(handler)

    data = client.update_status("user-1", "VERIFICADO")

    assert data.id == "user-1"
    assert data.status == "VERIFICADO"
    assert not hasattr(data, "password")
    assert not hasattr(data, "salt")


def test_update_status_without_user_block_returns_empty_data():
    """A response without the user block degrades to an empty value."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"msg": "ok"})

    client = _client(handler)

    data = client.update_status("user-1", "VERIFICADO")

    assert data == UpdatedUserData()


def test_update_status_with_unparsable_body_returns_empty_data():
    """A non JSON success body degrades to an empty value (the update held)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    client = _client(handler)

    data = client.update_status("user-1", "VERIFICADO")

    assert data == UpdatedUserData()


def test_update_status_404_raises_user_not_found():
    """A 404 from the Users service maps to UserNotFoundError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client(handler)

    with pytest.raises(UserNotFoundError) as raised:
        client.update_status("missing-user", "VERIFICADO")

    assert "missing-user" in str(raised.value)


@pytest.mark.parametrize("status_code", [400, 403, 500, 503])
def test_update_status_other_status_raises_unavailable(status_code):
    """Any answer other than 200 or 404 maps to UsersServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    client = _client(handler)

    with pytest.raises(UsersServiceUnavailableError):
        client.update_status("user-1", "NO_VERIFICADO")


def test_update_status_connection_error_raises_unavailable():
    """A transport failure maps to UsersServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client(handler)

    with pytest.raises(UsersServiceUnavailableError):
        client.update_status("user-1", "VERIFICADO")


def test_close_only_closes_owned_clients():
    """close() closes the internal client but not an injected one."""
    injected = httpx.Client(base_url="http://users.test")
    client = UsersServiceClient(client=injected)

    client.close()

    assert injected.is_closed is False

    owned = UsersServiceClient()
    owned.close()
    assert owned._client.is_closed is True
