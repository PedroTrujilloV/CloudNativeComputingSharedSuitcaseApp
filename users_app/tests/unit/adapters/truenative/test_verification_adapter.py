import json

import httpx
import pytest

from adapters.truenative.verification_adapter import TrueNativeVerificationAdapter
from domain.models.user import User
from errors import TrueNativeRequestError, TrueNativeUnreachableError


def _make_user(**overrides) -> User:
    data = {
        "username": "ana_user",
        "email": "ana@example.com",
        "dni": "123456",
        "fullName": "Ana Perez",
        "phoneNumber": "3001234567",
        "password": "hashed-password",
        "salt": "salt-value",
    }
    data.update(overrides)
    return User(**data)


def _adapter(handler) -> TrueNativeVerificationAdapter:
    return TrueNativeVerificationAdapter(transport=httpx.MockTransport(handler))


def _request(adapter, **user_overrides) -> str:
    return adapter.request_verification(
        user=_make_user(**user_overrides),
        user_identifier="user-1",
        transaction_identifier="tx-1",
    )


def test_request_verification_returns_ruv_from_201(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "secret-token")

    def handler(request):
        return httpx.Response(201, json={"RUV": "ruv-abc-123"})

    assert _request(_adapter(handler)) == "ruv-abc-123"


def test_request_verification_sends_expected_request(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "secret-token")
    monkeypatch.setenv("TRUE_NATIVE_BASE_URL", "http://truenative.test")
    monkeypatch.setenv("USER_WEBHOOK_URL", "http://callback.test/users/verify/callback")
    captured = {}

    def handler(request):
        captured["request"] = request
        return httpx.Response(201, json={"RUV": "ruv-abc-123"})

    _request(_adapter(handler))

    request = captured["request"]
    assert str(request.url) == "http://truenative.test/native/verify"
    assert request.method == "POST"
    assert request.headers["authorization"] == "Bearer secret-token"
    assert json.loads(request.content) == {
        "user": {
            "email": "ana@example.com",
            "dni": "123456",
            "fullName": "Ana Perez",
            "phone": "3001234567",
        },
        "userIdentifier": "user-1",
        "transactionIdentifier": "tx-1",
        "userWebhook": "http://callback.test/users/verify/callback",
    }


def test_request_verification_omits_empty_optional_fields(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "secret-token")
    captured = {}

    def handler(request):
        captured["request"] = request
        return httpx.Response(201, json={"RUV": "ruv-abc-123"})

    _request(
        _adapter(handler),
        dni=None,
        fullName=None,
        phoneNumber=None,
    )

    body = json.loads(captured["request"].content)
    assert body["user"] == {"email": "ana@example.com"}


def test_request_verification_defaults_to_in_cluster_base_url(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "secret-token")
    monkeypatch.delenv("TRUE_NATIVE_BASE_URL", raising=False)
    captured = {}

    def handler(request):
        captured["request"] = request
        return httpx.Response(201, json={"RUV": "ruv-abc-123"})

    _request(_adapter(handler))

    assert str(captured["request"].url) == "http://truenative-service/native/verify"


def test_request_verification_ignores_trailing_slash_in_base_url(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "secret-token")
    monkeypatch.setenv("TRUE_NATIVE_BASE_URL", "http://truenative.test/")
    captured = {}

    def handler(request):
        captured["request"] = request
        return httpx.Response(201, json={"RUV": "ruv-abc-123"})

    _request(_adapter(handler))

    assert str(captured["request"].url) == "http://truenative.test/native/verify"


@pytest.mark.parametrize("status_code", [400, 401, 403, 409, 500])
def test_request_verification_raises_request_error_for_http_errors(
    monkeypatch, status_code
):
    monkeypatch.setenv("SECRET_TOKEN", "secret-token")

    def handler(request):
        return httpx.Response(status_code, text="rejected")

    with pytest.raises(TrueNativeRequestError) as excinfo:
        _request(_adapter(handler))

    assert excinfo.value.status_code == status_code
    assert excinfo.value.detail == "rejected"


def test_request_verification_raises_unreachable_on_connect_error(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "secret-token")

    def handler(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(TrueNativeUnreachableError):
        _request(_adapter(handler))


def test_request_verification_raises_unreachable_when_201_has_no_ruv(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "secret-token")

    def handler(request):
        return httpx.Response(201, json={"ok": True})

    with pytest.raises(TrueNativeUnreachableError):
        _request(_adapter(handler))


def test_request_verification_raises_unreachable_when_201_is_not_json(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "secret-token")

    def handler(request):
        return httpx.Response(201, text="not json")

    with pytest.raises(TrueNativeUnreachableError):
        _request(_adapter(handler))
