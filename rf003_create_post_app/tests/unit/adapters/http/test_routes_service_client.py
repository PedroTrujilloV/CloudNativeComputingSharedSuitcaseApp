"""Unit tests for the Routes service HTTP client."""

import json
from datetime import datetime

import httpx
import pytest

from adapters.http.routes_service_client import RoutesServiceClient
from errors import RouteDatesInvalidError, RoutesServiceUnavailableError

BASE = "http://routes.test"


def _client(handler) -> RoutesServiceClient:
    transport = httpx.MockTransport(handler)
    return RoutesServiceClient(client=httpx.Client(base_url=BASE, transport=transport))


def _route_payload() -> dict:
    return {
        "id": "route-1",
        "flightId": "AA001",
        "sourceAirportCode": "BOG",
        "sourceCountry": "Colombia",
        "destinyAirportCode": "MAD",
        "destinyCountry": "Spain",
        "bagCost": 350,
        "plannedStartDate": "2026-10-01T10:00:00",
        "plannedEndDate": "2026-10-02T10:00:00",
        "createdAt": "2026-09-01T12:00:00",
        "updatedAt": None,
    }


def test_find_by_flight_id_returns_route_when_present():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["flight"] == "AA001"
        return httpx.Response(200, json=[_route_payload()])

    client = _client(handler)
    route = client.find_by_flight_id("AA001")

    assert route is not None
    assert route.id == "route-1"
    assert route.flightId == "AA001"
    assert route.plannedStartDate == datetime(2026, 10, 1, 10, 0, 0)


def test_find_by_flight_id_returns_none_when_absent():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _client(handler)
    assert client.find_by_flight_id("ZZ999") is None


def test_find_by_flight_id_unreachable_raises_503_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    with pytest.raises(RoutesServiceUnavailableError):
        client.find_by_flight_id("AA001")


def test_find_by_flight_id_non_200_raises_503_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    client = _client(handler)
    with pytest.raises(RoutesServiceUnavailableError):
        client.find_by_flight_id("AA001")


def test_create_route_sends_uppercased_airport_codes_and_returns_view():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            201, json={"id": "route-2", "createdAt": "2026-09-02T09:00:00"}
        )

    client = _client(handler)
    route = client.create_route(
        flight_id="AA002",
        source_airport_code="bog",
        source_country="Colombia",
        destiny_airport_code="mad",
        destiny_country="Spain",
        bag_cost=100,
        planned_start_date=datetime(2026, 10, 1, 10, 0),
        planned_end_date=datetime(2026, 10, 2, 10, 0),
    )

    assert route.id == "route-2"
    assert route.flightId == "AA002"
    assert route.createdAt == datetime(2026, 9, 2, 9, 0, 0)
    assert seen["body"]["sourceAirportCode"] == "BOG"
    assert seen["body"]["destinyAirportCode"] == "MAD"
    assert seen["body"]["flightId"] == "AA002"
    assert seen["body"]["plannedStartDate"] == "2026-10-01T10:00:00"


def test_create_route_412_raises_route_dates_invalid():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            412, json={"msg": "Las fechas del trayecto no son válidas"}
        )

    client = _client(handler)
    with pytest.raises(RouteDatesInvalidError):
        client.create_route(
            flight_id="AA003",
            source_airport_code="BOG",
            source_country="Colombia",
            destiny_airport_code="MAD",
            destiny_country="Spain",
            bag_cost=100,
            planned_start_date=datetime(2020, 1, 1),
            planned_end_date=datetime(2020, 1, 2),
        )


def test_create_route_unreachable_raises_503_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    with pytest.raises(RoutesServiceUnavailableError):
        client.create_route(
            flight_id="AA004",
            source_airport_code="BOG",
            source_country="Colombia",
            destiny_airport_code="MAD",
            destiny_country="Spain",
            bag_cost=100,
            planned_start_date=datetime(2026, 10, 1),
            planned_end_date=datetime(2026, 10, 2),
        )


def test_create_route_unexpected_status_raises_503_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={})

    client = _client(handler)
    with pytest.raises(RoutesServiceUnavailableError):
        client.create_route(
            flight_id="AA005",
            source_airport_code="BOG",
            source_country="Colombia",
            destiny_airport_code="MAD",
            destiny_country="Spain",
            bag_cost=100,
            planned_start_date=datetime(2026, 10, 1),
            planned_end_date=datetime(2026, 10, 2),
        )


def test_delete_route_sends_delete_to_route_endpoint():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json={"msg": "el trayecto fue eliminado"})

    client = _client(handler)
    client.delete_route("route-1")

    assert seen["method"] == "DELETE"
    assert seen["path"] == "/routes/route-1"


def test_delete_route_404_is_treated_as_success():
    """A route that no longer exists needs no further compensation."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={})

    client = _client(handler)
    client.delete_route("route-gone")  # must not raise


def test_delete_route_unreachable_raises_503_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    with pytest.raises(RoutesServiceUnavailableError):
        client.delete_route("route-1")


def test_delete_route_unexpected_status_raises_503_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    client = _client(handler)
    with pytest.raises(RoutesServiceUnavailableError):
        client.delete_route("route-1")
