"""Unit tests for the Offers service HTTP client (offer creation)."""

import json

import httpx
import pytest

from adapters.http.offers_service_client import OffersServiceClient
from errors import OffersServiceUnavailableError

BASE = "http://offers.test"


def _client(handler) -> OffersServiceClient:
    transport = httpx.MockTransport(handler)
    return OffersServiceClient(client=httpx.Client(base_url=BASE, transport=transport))


def test_create_offer_success_returns_dict():
    """A 201 from POST /offers returns the parsed offer view."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/offers"
        payload = json.loads(request.content)
        assert payload["postId"] == "post-1"
        assert payload["userId"] == "user-1"
        assert payload["description"] == "Space for one medium bag"
        assert payload["size"] == "MEDIUM"
        assert payload["fragile"] is False
        assert payload["offer"] == 50000.0
        return httpx.Response(
            201,
            json={
                "id": "offer-1",
                "userId": "user-1",
                "createdAt": "2026-09-01T10:00:00Z",
                "postId": "post-1",
            },
        )

    client = _client(handler)
    result = client.create_offer(
        postId="post-1",
        userId="user-1",
        description="Space for one medium bag",
        size="MEDIUM",
        fragile=False,
        offer=50000.0,
    )

    assert result["id"] == "offer-1"
    assert result["postId"] == "post-1"


def test_create_offer_412_raises_unavailable():
    """A 412 from the Offers service maps to OffersServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(412, json={"msg": "La oferta no fue aceptada"})

    client = _client(handler)
    with pytest.raises(OffersServiceUnavailableError):
        client.create_offer(
            postId="post-1",
            userId="user-1",
            description="Space for one medium bag",
            size="MEDIUM",
            fragile=False,
            offer=50000.0,
        )


def test_create_offer_5xx_raises_unavailable():
    """A 5xx from the Offers service maps to OffersServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"msg": "internal error"})

    client = _client(handler)
    with pytest.raises(OffersServiceUnavailableError):
        client.create_offer(
            postId="post-1",
            userId="user-1",
            description="Space for one medium bag",
            size="MEDIUM",
            fragile=False,
            offer=50000.0,
        )


def test_create_offer_network_error_raises_unavailable():
    """A network error maps to OffersServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client(handler)
    with pytest.raises(OffersServiceUnavailableError):
        client.create_offer(
            postId="post-1",
            userId="user-1",
            description="Space for one medium bag",
            size="MEDIUM",
            fragile=False,
            offer=50000.0,
        )


def test_delete_offer_success():
    """A 200 from DELETE /offers/{id} returns None."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/offers/offer-1"
        return httpx.Response(200, json={"msg": "la oferta fue eliminada"})

    client = _client(handler)
    assert client.delete_offer("offer-1") is None


def test_delete_offer_404_raises_unavailable():
    """A 404 from the Offers service maps to OffersServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client(handler)
    with pytest.raises(OffersServiceUnavailableError):
        client.delete_offer("offer-1")


def test_delete_offer_network_error_raises_unavailable():
    """A network error maps to OffersServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client(handler)
    with pytest.raises(OffersServiceUnavailableError):
        client.delete_offer("offer-1")
