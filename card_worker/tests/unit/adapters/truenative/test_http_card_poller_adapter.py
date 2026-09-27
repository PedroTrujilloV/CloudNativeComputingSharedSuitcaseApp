import httpx2
import pytest

from adapters.truenative import http_card_poller_adapter
from adapters.truenative.http_card_poller_adapter import HttpCardPollerAdapter
from errors import TrueNativePollingError

BASE_URL = "http://truenative.test"
SECRET = "the-secret-token"


def build_adapter(handler) -> HttpCardPollerAdapter:
    transport = httpx2.MockTransport(handler)
    return HttpCardPollerAdapter(
        base_url=BASE_URL,
        secret_token=SECRET,
        client_factory=lambda: httpx2.Client(transport=transport),
    )


def handler_returning(status_code: int, body=None):
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "GET"
        assert request.url.path == "/native/cards/ruv-1"
        if body is not None:
            return httpx2.Response(status_code, json=body, request=request)
        return httpx2.Response(status_code, request=request)

    return handler


def test_a_202_answer_is_not_terminal():
    adapter = build_adapter(handler_returning(202))
    result = adapter.check_status("ruv-1")
    assert result.terminal is False
    assert result.status is None


def test_a_200_with_aprobada_is_terminal():
    adapter = build_adapter(handler_returning(200, {"RUV": "ruv-1", "status": "APROBADA"}))
    result = adapter.check_status("ruv-1")
    assert result.terminal is True
    assert result.status == "APROBADA"


def test_a_200_with_rechazada_is_terminal():
    adapter = build_adapter(handler_returning(200, {"RUV": "ruv-1", "status": "RECHAZADA"}))
    result = adapter.check_status("ruv-1")
    assert result.terminal is True
    assert result.status == "RECHAZADA"


def test_a_200_with_an_unexpected_status_normalizes_the_case():
    adapter = build_adapter(handler_returning(200, {"RUV": "ruv-1", "status": " aprobada "}))
    result = adapter.check_status("ruv-1")
    assert result.terminal is True
    assert result.status == "APROBADA"


def test_the_request_carries_the_bearer_token_and_the_ruv_path():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["authorization"] = request.headers.get("authorization")
        seen["path"] = request.url.path
        return httpx2.Response(202, request=request)

    adapter = build_adapter(handler)
    adapter.check_status("ruv-1")

    assert seen["authorization"] == f"Bearer {SECRET}"
    assert seen["path"] == "/native/cards/ruv-1"


def test_an_unknown_terminal_status_raises():
    adapter = build_adapter(handler_returning(200, {"RUV": "ruv-1", "status": "UNKNOWN"}))

    with pytest.raises(TrueNativePollingError):
        adapter.check_status("ruv-1")


def test_a_200_answer_without_a_status_raises():
    adapter = build_adapter(handler_returning(200, {"RUV": "ruv-1"}))

    with pytest.raises(TrueNativePollingError):
        adapter.check_status("ruv-1")


def test_an_unauthorized_answer_raises():
    adapter = build_adapter(handler_returning(401, {"message": "bad secret"}))

    with pytest.raises(TrueNativePollingError):
        adapter.check_status("ruv-1")


def test_a_platform_failure_raises():
    adapter = build_adapter(handler_returning(500, {"message": "boom"}))

    with pytest.raises(TrueNativePollingError):
        adapter.check_status("ruv-1")


def test_an_unparseable_answer_raises():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            content=b"not json",
            request=request,
            headers={"Content-Type": "text/plain"},
        )

    adapter = build_adapter(handler)

    with pytest.raises(TrueNativePollingError):
        adapter.check_status("ruv-1")


def test_a_non_object_answer_raises():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=["APROBADA"], request=request)

    adapter = build_adapter(handler)

    with pytest.raises(TrueNativePollingError):
        adapter.check_status("ruv-1")


def test_a_network_failure_raises():
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused")

    adapter = build_adapter(handler)

    with pytest.raises(TrueNativePollingError):
        adapter.check_status("ruv-1")


# ---------------------------------------------------------------------------
# Base URL resolution (explicit env var vs Lambda discovery vs local default)
# ---------------------------------------------------------------------------


def test_an_explicit_truenative_url_wins_over_the_discovery(monkeypatch):
    monkeypatch.setenv("TRUENATIVE_URL", "http://explicit.test")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "card-worker")

    adapter = HttpCardPollerAdapter()

    assert adapter.base_url == "http://explicit.test"


def test_on_lambda_without_an_explicit_url_the_host_is_discovered(monkeypatch):
    monkeypatch.delenv("TRUENATIVE_URL")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "card-worker")
    monkeypatch.setattr(
        http_card_poller_adapter.ingress_discovery,
        "discover_truenative_base_url",
        lambda: "https://discovered.test",
    )

    adapter = HttpCardPollerAdapter()

    assert adapter.base_url == "https://discovered.test"


def test_off_lambda_without_an_explicit_url_uses_the_in_cluster_service(
    monkeypatch,
):
    monkeypatch.delenv("TRUENATIVE_URL")
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)

    adapter = HttpCardPollerAdapter()

    assert adapter.base_url == "http://truenative-service"
