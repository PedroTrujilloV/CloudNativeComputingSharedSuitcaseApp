"""Unit tests for POST /routes endpoint."""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import MagicMock, patch

from entrypoints.api.main import app
from domain.models.route import Route, RouteCreateRequest, RouteCreateResponse
from domain.ports.route_repository_port import RouteRepositoryPort
from errors import RouteAlreadyExistsError


def _future_iso(days_ahead: int) -> str:
    """Return an ISO-8601 UTC datetime string days ahead."""
    return (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()


def _past_iso(days_ago: int) -> str:
    """Return an ISO-8601 UTC datetime string days ago."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class MockRouteRepository(RouteRepositoryPort):
    """Mock route repository for testing."""

    def __init__(self):
        self.routes = {}
        self.counter = 0

    def create(self, route: Route) -> Route:
        """Create a route."""
        self.counter += 1
        route.id = f"route-{self.counter}"
        route.createdAt = datetime.now(timezone.utc)
        route.updatedAt = datetime.now(timezone.utc)
        self.routes[route.id] = route
        self.routes[route.flightId] = route
        return route

    def get_by_id(self, route_id: str) -> Route | None:
        """Get route by id."""
        return self.routes.get(route_id)

    def get_by_flight_id(self, flight_id: str) -> Route | None:
        """Get route by flightId."""
        return self.routes.get(flight_id)

    def list_routes(self, flight_id=None):
        """List all routes, optionally filtered by flightId."""
        if flight_id:
            route = self.routes.get(flight_id)
            return [route] if route else []
        return list({r.id: r for r in self.routes.values()}.values())

    def delete(self, route):
        """Delete a route."""
        if route.id in self.routes:
            del self.routes[route.id]
            return True
        return False

    def delete_by_id(self, route_id: str) -> bool:
        """Delete a route by its UUID."""
        if route_id in self.routes:
            del self.routes[route_id]
            return True
        return False

    def count(self) -> int:
        """Count routes."""
        return len(self.routes)

    def delete_all(self) -> None:
        """Delete all routes."""
        self.routes.clear()


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    return MockRouteRepository()


@pytest.fixture
def sample_route_data():
    """Sample route creation data."""
    future_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
    future_end_date = (datetime.utcnow() + timedelta(days=10)).isoformat()
    return {
        "flightId": "TEST123",
        "sourceAirportCode": "BOG",
        "sourceCountry": "Colombia",
        "destinyAirportCode": "LGW",
        "destinyCountry": "United Kingdom",
        "bagCost": 126,
        "plannedStartDate": future_date,
        "plannedEndDate": future_end_date,
    }


def test_create_route_success(client, mock_repository, monkeypatch):
    """Test successful route creation."""
    # Patch the get_repository function
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    response = client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "LGW",
            "destinyCountry": "United Kingdom",
            "bagCost": 126,
            "plannedStartDate": _future_iso(1),
            "plannedEndDate": _future_iso(10),
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "createdAt" in data


def test_create_route_missing_field(client, mock_repository, monkeypatch):
    """Test that missing required field returns 400."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    response = client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "LGW",
            "destinyCountry": "United Kingdom",
            "bagCost": 126,
            # Missing plannedStartDate and plannedEndDate
        },
    )

    assert response.status_code == 400


def test_create_route_duplicate_flight_id(client, mock_repository, monkeypatch):
    """Test that duplicate flightId returns 412."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "LGW",
            "destinyCountry": "United Kingdom",
            "bagCost": 126,
            "plannedStartDate": _future_iso(1),
            "plannedEndDate": _future_iso(10),
        },
    )

    response = client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "JFK",
            "destinyCountry": "USA",
            "bagCost": 100,
            "plannedStartDate": _future_iso(1),
            "plannedEndDate": _future_iso(10),
        },
    )

    assert response.status_code == 412


def test_create_route_invalid_dates_past(client, mock_repository, monkeypatch):
    """Test that past dates return 412 with correct message."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    past_date = _past_iso(1)
    past_end_date = _past_iso(2)

    response = client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "LGW",
            "destinyCountry": "United Kingdom",
            "bagCost": 126,
            "plannedStartDate": past_date,
            "plannedEndDate": past_end_date,
        },
    )

    assert response.status_code == 412
    assert response.json()["msg"] == "Las fechas del trayecto no son válidas"


def test_create_route_invalid_dates_not_consecutive(client, mock_repository, monkeypatch):
    """Test that end date before start date returns 412."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    future_date = _future_iso(10)
    earlier_date = _future_iso(1)

    response = client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "LGW",
            "destinyCountry": "United Kingdom",
            "bagCost": 126,
            "plannedStartDate": future_date,
            "plannedEndDate": earlier_date,
        },
    )

    assert response.status_code == 412
    assert response.json()["msg"] == "Las fechas del trayecto no son válidas"


def test_create_route_duplicate_flight_id_message(client, mock_repository, monkeypatch):
    """Test that duplicate flightId returns 412 with N/A body."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "LGW",
            "destinyCountry": "United Kingdom",
            "bagCost": 126,
            "plannedStartDate": _future_iso(1),
            "plannedEndDate": _future_iso(10),
        },
    )

    response = client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "JFK",
            "destinyCountry": "USA",
            "bagCost": 100,
            "plannedStartDate": _future_iso(1),
            "plannedEndDate": _future_iso(10),
        },
    )

    assert response.status_code == 412
    assert response.json() == {}


def test_create_route_invalid_airport_code(client, mock_repository, monkeypatch):
    """Test that invalid airport code returns 400."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    future_date = _future_iso(1)
    future_end_date = _future_iso(10)

    response = client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BO",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "LGW",
            "destinyCountry": "United Kingdom",
            "bagCost": 126,
            "plannedStartDate": future_date,
            "plannedEndDate": future_end_date,
        },
    )

    assert response.status_code == 400


def test_get_routes_all(client, mock_repository, monkeypatch):
    """Test that GET /routes returns all routes."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    # Create two routes first
    client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "LGW",
            "destinyCountry": "United Kingdom",
            "bagCost": 126,
            "plannedStartDate": _future_iso(1),
            "plannedEndDate": _future_iso(10),
        },
    )
    client.post(
        "/routes",
        json={
            "flightId": "TEST456",
            "sourceAirportCode": "JFK",
            "sourceCountry": "USA",
            "destinyAirportCode": "LHR",
            "destinyCountry": "United Kingdom",
            "bagCost": 200,
            "plannedStartDate": _future_iso(5),
            "plannedEndDate": _future_iso(15),
        },
    )

    response = client.get("/routes")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_routes_filter_by_flight_id(client, mock_repository, monkeypatch):
    """Test that GET /routes?flight=XXX returns filtered routes."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    # Create two routes with different flightIds
    client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "LGW",
            "destinyCountry": "United Kingdom",
            "bagCost": 126,
            "plannedStartDate": _future_iso(1),
            "plannedEndDate": _future_iso(10),
        },
    )
    client.post(
        "/routes",
        json={
            "flightId": "TEST456",
            "sourceAirportCode": "JFK",
            "sourceCountry": "USA",
            "destinyAirportCode": "LHR",
            "destinyCountry": "United Kingdom",
            "bagCost": 200,
            "plannedStartDate": _future_iso(5),
            "plannedEndDate": _future_iso(15),
        },
    )

    response = client.get("/routes?flight=TEST123")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["flightId"] == "TEST123"


def test_get_routes_empty(client, mock_repository, monkeypatch):
    """Test that GET /routes returns empty list when no routes exist."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    response = client.get("/routes")
    assert response.status_code == 200
    assert response.json() == []


def test_get_routes_filter_by_flight_id_not_found(client, mock_repository, monkeypatch):
    """Test that GET /routes?flight=XXX returns empty list when no match."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    # Create a route
    client.post(
        "/routes",
        json={
            "flightId": "TEST123",
            "sourceAirportCode": "BOG",
            "sourceCountry": "Colombia",
            "destinyAirportCode": "LGW",
            "destinyCountry": "United Kingdom",
            "bagCost": 126,
            "plannedStartDate": _future_iso(1),
            "plannedEndDate": _future_iso(10),
        },
    )

    response = client.get("/routes?flight=NONEXISTENT")
    assert response.status_code == 200
    assert response.json() == []


def test_get_route_by_id_valid_id(client, mock_repository, monkeypatch):
    """Test that GET /routes/{id} returns the route when a valid UUID is provided."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
    mock_repository.routes[valid_uuid] = Route(
        id=valid_uuid,
        flightId="TEST123",
        sourceAirportCode="BOG",
        sourceCountry="Colombia",
        destinyAirportCode="LGW",
        destinyCountry="United Kingdom",
        bagCost=126,
        plannedStartDate=datetime.now(timezone.utc) + timedelta(days=1),
        plannedEndDate=datetime.now(timezone.utc) + timedelta(days=10),
        createdAt=datetime.now(timezone.utc),
    )

    response = client.get(f"/routes/{valid_uuid}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == valid_uuid
    assert data["flightId"] == "TEST123"
    assert data["sourceAirportCode"] == "BOG"
    assert data["destinyAirportCode"] == "LGW"
    assert data["bagCost"] == 126


def test_get_route_by_id_invalid_uuid_format(client, mock_repository, monkeypatch):
    """Test that GET /routes/{id} returns 400 when id is not a valid UUID format."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    response = client.get("/routes/not-a-uuid")
    assert response.status_code == 400
    assert response.json() == {}


def test_get_route_by_id_invalid_uuid_numeric(client, mock_repository, monkeypatch):
    """Test that GET /routes/{id} returns 400 when id is a numeric string."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    response = client.get("/routes/123")
    assert response.status_code == 400
    assert response.json() == {}


def test_delete_route_success(client, mock_repository, monkeypatch):
    """Test that DELETE /routes/{id} returns 200 with success message for valid UUID."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    valid_uuid = "550e8400-e29b-41d4-a716-446655440001"
    mock_repository.routes[valid_uuid] = Route(
        id=valid_uuid,
        flightId="TEST456",
        sourceAirportCode="JFK",
        sourceCountry="USA",
        destinyAirportCode="LHR",
        destinyCountry="United Kingdom",
        bagCost=200,
        plannedStartDate=datetime.now(timezone.utc) + timedelta(days=1),
        plannedEndDate=datetime.now(timezone.utc) + timedelta(days=10),
        createdAt=datetime.now(timezone.utc),
    )

    response = client.delete(f"/routes/{valid_uuid}")
    assert response.status_code == 200
    data = response.json()
    assert data == {"msg": "el trayecto fue eliminado"}

    # Verify route was actually deleted
    assert valid_uuid not in mock_repository.routes


def test_get_route_by_id_not_found(client, mock_repository, monkeypatch):
    """Test that GET /routes/{id} returns 404 when no route exists for the given id."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    response = client.get("/routes/99999999-9999-9999-9999-999999999999")
    assert response.status_code == 404
    assert response.json() == {}


def test_delete_route_invalid_uuid_format(client, mock_repository, monkeypatch):
    """Test that DELETE /routes/{id} returns 400 when id is not a valid UUID format."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    response = client.delete("/routes/not-a-uuid")
    assert response.status_code == 400
    assert response.json() == {}


def test_delete_route_not_found(client, mock_repository, monkeypatch):
    """Test that DELETE /routes/{id} returns 404 when no route exists for the given id."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    non_existent_uuid = "00000000-0000-0000-0000-000000000000"
    response = client.delete(f"/routes/{non_existent_uuid}")
    assert response.status_code == 404
    assert response.json() == {}


def test_delete_route_idempotency(client, mock_repository, monkeypatch):
    """Test that double deletion returns 404 on second call."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    valid_uuid = "550e8400-e29b-41d4-a716-446655440002"
    mock_repository.routes[valid_uuid] = Route(
        id=valid_uuid,
        flightId="TEST789",
        sourceAirportCode="MAD",
        sourceCountry="Spain",
        destinyAirportCode="CDG",
        destinyCountry="France",
        bagCost=150,
        plannedStartDate=datetime.now(timezone.utc) + timedelta(days=1),
        plannedEndDate=datetime.now(timezone.utc) + timedelta(days=10),
        createdAt=datetime.now(timezone.utc),
    )

    # First deletion should succeed
    response = client.delete(f"/routes/{valid_uuid}")
    assert response.status_code == 200

    # Second deletion should return 404
    response = client.delete(f"/routes/{valid_uuid}")
    assert response.status_code == 404
    assert response.json() == {}


def test_count_routes_empty_db(client, mock_repository, monkeypatch):
    """Test that GET /routes/count returns {"count": 0} when no routes exist."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    response = client.get("/routes/count")
    assert response.status_code == 200
    assert response.json() == {"count": 0}


def test_count_routes_with_routes(client, mock_repository, monkeypatch):
    """Test that GET /routes/count returns correct count when routes exist."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    mock_repository.routes["route-1"] = Route(
        id="route-1",
        flightId="TEST123",
        sourceAirportCode="BOG",
        sourceCountry="Colombia",
        destinyAirportCode="LGW",
        destinyCountry="United Kingdom",
        bagCost=126,
        plannedStartDate=datetime.now(timezone.utc) + timedelta(days=1),
        plannedEndDate=datetime.now(timezone.utc) + timedelta(days=10),
        createdAt=datetime.now(timezone.utc),
    )
    mock_repository.routes["route-2"] = Route(
        id="route-2",
        flightId="TEST456",
        sourceAirportCode="JFK",
        sourceCountry="USA",
        destinyAirportCode="LHR",
        destinyCountry="United Kingdom",
        bagCost=200,
        plannedStartDate=datetime.now(timezone.utc) + timedelta(days=1),
        plannedEndDate=datetime.now(timezone.utc) + timedelta(days=10),
        createdAt=datetime.now(timezone.utc),
    )
    mock_repository.routes["route-3"] = Route(
        id="route-3",
        flightId="TEST789",
        sourceAirportCode="MAD",
        sourceCountry="Spain",
        destinyAirportCode="CDG",
        destinyCountry="France",
        bagCost=150,
        plannedStartDate=datetime.now(timezone.utc) + timedelta(days=1),
        plannedEndDate=datetime.now(timezone.utc) + timedelta(days=10),
        createdAt=datetime.now(timezone.utc),
    )

    response = client.get("/routes/count")
    assert response.status_code == 200
    assert response.json() == {"count": 3}


def test_count_routes_after_delete(client, mock_repository, monkeypatch):
    """Test that count decrements after deleting routes."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    valid_uuid = "550e8400-e29b-41d4-a716-446655440003"
    mock_repository.routes[valid_uuid] = Route(
        id=valid_uuid,
        flightId="TEST111",
        sourceAirportCode="BOG",
        sourceCountry="Colombia",
        destinyAirportCode="JFK",
        destinyCountry="USA",
        bagCost=100,
        plannedStartDate=datetime.now(timezone.utc) + timedelta(days=1),
        plannedEndDate=datetime.now(timezone.utc) + timedelta(days=10),
        createdAt=datetime.now(timezone.utc),
    )

    # Count should be 1
    response = client.get("/routes/count")
    assert response.status_code == 200
    assert response.json() == {"count": 1}

    # Delete the route
    client.delete(f"/routes/{valid_uuid}")

    # Count should be 0
    response = client.get("/routes/count")
    assert response.status_code == 200
    assert response.json() == {"count": 0}


def test_reset_routes_empty_db(client, mock_repository, monkeypatch):
    """Test that POST /routes/reset on empty database returns 200 with correct message."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    response = client.post("/routes/reset")
    assert response.status_code == 200
    assert response.json() == {"msg": "Todos los datos fueron eliminados"}


def test_reset_routes_with_data(client, mock_repository, monkeypatch):
    """Test that POST /routes/reset clears all routes and count becomes 0."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    mock_repository.routes["route-1"] = Route(
        id="route-1",
        flightId="TEST123",
        sourceAirportCode="BOG",
        sourceCountry="Colombia",
        destinyAirportCode="LGW",
        destinyCountry="United Kingdom",
        bagCost=126,
        plannedStartDate=datetime.now(timezone.utc) + timedelta(days=1),
        plannedEndDate=datetime.now(timezone.utc) + timedelta(days=10),
        createdAt=datetime.now(timezone.utc),
    )
    mock_repository.routes["route-2"] = Route(
        id="route-2",
        flightId="TEST456",
        sourceAirportCode="JFK",
        sourceCountry="USA",
        destinyAirportCode="LHR",
        destinyCountry="United Kingdom",
        bagCost=200,
        plannedStartDate=datetime.now(timezone.utc) + timedelta(days=1),
        plannedEndDate=datetime.now(timezone.utc) + timedelta(days=10),
        createdAt=datetime.now(timezone.utc),
    )
    mock_repository.routes["route-3"] = Route(
        id="route-3",
        flightId="TEST789",
        sourceAirportCode="MAD",
        sourceCountry="Spain",
        destinyAirportCode="CDG",
        destinyCountry="France",
        bagCost=150,
        plannedStartDate=datetime.now(timezone.utc) + timedelta(days=1),
        plannedEndDate=datetime.now(timezone.utc) + timedelta(days=10),
        createdAt=datetime.now(timezone.utc),
    )

    assert mock_repository.count() == 3

    response = client.post("/routes/reset")
    assert response.status_code == 200
    assert response.json() == {"msg": "Todos los datos fueron eliminados"}

    # Verify count is now 0
    response = client.get("/routes/count")
    assert response.status_code == 200
    assert response.json() == {"count": 0}


def test_reset_routes_idempotency(client, mock_repository, monkeypatch):
    """Test that calling POST /routes/reset twice returns 200 both times."""
    def mock_get_repository():
        return mock_repository

    monkeypatch.setattr(
        "entrypoints.api.routers.routes_router.get_repository",
        mock_get_repository,
    )

    # First reset on already empty database
    response = client.post("/routes/reset")
    assert response.status_code == 200
    assert response.json() == {"msg": "Todos los datos fueron eliminados"}

    # Second reset should also return 200
    response = client.post("/routes/reset")
    assert response.status_code == 200
    assert response.json() == {"msg": "Todos los datos fueron eliminados"}