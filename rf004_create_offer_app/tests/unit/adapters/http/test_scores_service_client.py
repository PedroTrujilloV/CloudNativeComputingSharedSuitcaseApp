"""Unit tests for the Scores service HTTP client (score persistence)."""

import json

import httpx
import pytest

from adapters.http.scores_service_client import ScoresServiceClient
from errors import ScoresServiceUnavailableError

BASE = "http://scores.test"


def _client(handler) -> ScoresServiceClient:
    transport = httpx.MockTransport(handler)
    return ScoresServiceClient(client=httpx.Client(base_url=BASE, transport=transport))


def test_upsert_score_success_returns_dict():
    """A 201 from POST /scores returns the parsed score view."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/scores"
        payload = json.loads(request.content)
        assert payload["offerId"] == "offer-1"
        assert payload["score"] == 45000.0
        return httpx.Response(
            201,
            json={"offerId": "offer-1", "score": 45000.0},
        )

    client = _client(handler)
    result = client.upsert_score(offer_id="offer-1", score_value=45000.0)

    assert result["offerId"] == "offer-1"
    assert result["score"] == 45000.0


def test_upsert_score_5xx_raises_unavailable():
    """A 5xx from the Scores service maps to ScoresServiceUnavailableError (soft-fail)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"msg": "internal error"})

    client = _client(handler)
    with pytest.raises(ScoresServiceUnavailableError):
        client.upsert_score(offer_id="offer-1", score_value=45000.0)


def test_upsert_score_4xx_raises_unavailable():
    """A 4xx from the Scores service maps to ScoresServiceUnavailableError (soft-fail)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"msg": "bad request"})

    client = _client(handler)
    with pytest.raises(ScoresServiceUnavailableError):
        client.upsert_score(offer_id="offer-1", score_value=45000.0)


def test_upsert_score_network_error_raises_unavailable():
    """A network error maps to ScoresServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client(handler)
    with pytest.raises(ScoresServiceUnavailableError):
        client.upsert_score(offer_id="offer-1", score_value=45000.0)
