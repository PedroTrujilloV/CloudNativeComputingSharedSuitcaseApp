"""Test suite for ScoresServiceClient (RF-005 score resilience).

The RF-005 resilience requirement is exercised here: a score that is
missing, or a Score service that is temporarily down (network error,
timeout, 5xx, malformed payload), must degrade to ``None`` for the
individual offer. The client must never raise, so the orchestrator can
answer 200 with ``score: null`` for the affected offer.
"""

import httpx
import pytest
from unittest.mock import Mock

from adapters.http.scores_service_client import ScoresServiceClient


def _client_with(response=None, side_effect=None):
    mock_client = Mock()
    if side_effect is not None:
        mock_client.get.side_effect = side_effect
    else:
        mock_client.get.return_value = response
    return ScoresServiceClient(client=mock_client)


def _response(status_code, json_payload=None, raise_on_json=False):
    mock_response = Mock()
    mock_response.status_code = status_code
    if raise_on_json:
        mock_response.json.side_effect = ValueError("not json")
    else:
        mock_response.json.return_value = json_payload
    return mock_response


class TestGetScoreSuccess:
    """Happy path: the score exists and is returned as a float."""

    def test_returns_score_when_present(self):
        service = _client_with(
            _response(200, {"offerId": "o1", "score": 4.8})
        )
        assert service.get_score("o1") == 4.8

    def test_returns_int_score_as_float(self):
        service = _client_with(_response(200, {"offerId": "o1", "score": 5}))
        assert service.get_score("o1") == 5.0


class TestGetScoreMissing:
    """A score that does not exist degrades to None (no error)."""

    def test_returns_none_when_score_field_is_null(self):
        service = _client_with(
            _response(200, {"offerId": "o1", "score": None})
        )
        assert service.get_score("o1") is None

    def test_returns_none_on_404(self):
        service = _client_with(_response(404, {}))
        assert service.get_score("o1") is None


class TestGetScoreServiceDown:
    """A Score service outage degrades to None per offer (never raises)."""

    def test_returns_none_on_connection_error(self):
        service = _client_with(
            side_effect=httpx.ConnectError("connection refused")
        )
        assert service.get_score("o1") is None

    def test_returns_none_on_read_timeout(self):
        service = _client_with(
            side_effect=httpx.ReadTimeout("timed out")
        )
        assert service.get_score("o1") is None

    def test_returns_none_on_500(self):
        service = _client_with(_response(500, {}))
        assert service.get_score("o1") is None

    def test_returns_none_on_503(self):
        service = _client_with(_response(503, {}))
        assert service.get_score("o1") is None


class TestGetScoreMalformedPayload:
    """Malformed payloads degrade to None (never raise)."""

    def test_returns_none_when_body_is_not_json(self):
        service = _client_with(_response(200, raise_on_json=True))
        assert service.get_score("o1") is None

    def test_returns_none_when_score_is_not_numeric(self):
        service = _client_with(
            _response(200, {"offerId": "o1", "score": "not-a-number"})
        )
        assert service.get_score("o1") is None
