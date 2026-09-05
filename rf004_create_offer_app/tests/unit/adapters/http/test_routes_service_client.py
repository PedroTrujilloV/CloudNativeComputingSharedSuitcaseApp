"""Unit tests for the Routes service HTTP client (route lookup)."""

import httpx
import pytest

from adapters.http.routes_service_client import RoutesServiceClient
from errors import RouteNotFoundError, RoutesServiceUnavailableError

BASE = "http://routes.test"


def _client(handler) -> RoutesServiceClient:
    transport = httpx.MockTransport(handler)
    return RoutesServiceClient(client=httpx.Client(base_url=BASE, transport=transport))


def test_get_route_success_returns_route_info():
    """A 200 from GET /routes/{id} maps to a RouteInfo view."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/routes/route-1"
        return httpx.Response(
            200,
            json={
                "id": "route-1",
                "bagCost": 10000.0,
            },
        )

    client = _client(handler)
    route = client.get_route("route-1")

    assert route.id == "route-1"
    assert route.bagCost == 10000.0


def test_get_route_404_raises_not_found():
    """A 404 from the Routes service maps to RouteNotFoundError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"msg": "La ruta no existe"})

    client = _client(handler)
    with pytest.raises(RouteNotFoundError):
        client.get_route("missing")


def test_get_route_5xx_raises_unavailable():
    """A 5xx from the Routes service maps to RoutesServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"msg": "internal error"})

    client = _client(handler)
    with pytest.raises(RoutesServiceUnavailableError):
        client.get_route("route-1")


def test_get_route_network_error_raises_unavailable():
    """A network error maps to RoutesServiceUnavailableError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = _client(handler)
    with pytest.raises(RoutesServiceUnavailableError):
        client.get_route("route-1")
