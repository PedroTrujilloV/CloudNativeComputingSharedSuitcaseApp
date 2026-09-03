"""Test helpers for the RF-003 orchestrator."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from domain.models.route import RouteInfo
from domain.ports.posts_port import CreatedPost
from domain.ports.user_validation_port import AuthenticatedUser
from domain.use_cases.create_post_use_case import CreatePostUseCase
from domain.use_cases.validate_token_use_case import ValidateTokenUseCase
from entrypoints.api.deps import (
    get_create_post_use_case,
    get_validate_token_use_case,
)
from entrypoints.api.main import app


def valid_payload(**overrides) -> dict:
    """A well-formed RF-003 request body.

    ``expireAt`` must be in the future and on/before ``plannedStartDate``
    for the core orchestration to accept it (RF-003 rule).
    """
    payload = {
        "flightId": "AA001",
        "expireAt": "2026-09-15T10:00:00",
        "plannedStartDate": "2026-10-01T10:00:00",
        "plannedEndDate": "2026-10-02T10:00:00",
        "origin": {"airportCode": "BOG", "country": "Colombia"},
        "destiny": {"airportCode": "MAD", "country": "Spain"},
        "bagCost": 350,
    }
    payload.update(overrides)
    return payload


class FakeUserValidation:
    """In-memory stand-in for the Users service token validation."""

    def __init__(self, token: str = "valid-token", user_id: str | None = None):
        self.token = token
        self.user_id = user_id or str(uuid4())
        self.calls: list[str] = []

    def validate_token(self, token: str) -> AuthenticatedUser:
        self.calls.append(token)
        if token != self.token:
            from errors import InvalidTokenError

            raise InvalidTokenError("Invalid or expired token")
        return AuthenticatedUser(id=self.user_id, username="tester")


class FakeRoutes:
    """In-memory stand-in for the Routes service client."""

    def __init__(self, existing_route: RouteInfo | None = None):
        self.existing_route = existing_route
        self.created: list[dict] = []
        self.created_ids: list[str] = []
        self.find_calls: list[str] = []
        self.deleted: list[str] = []
        self.delete_error: Exception | None = None

    def find_by_flight_id(self, flight_id: str) -> RouteInfo | None:
        self.find_calls.append(flight_id)
        if (
            self.existing_route is not None
            and self.existing_route.flightId == flight_id
        ):
            return self.existing_route
        return None

    def delete_route(self, route_id: str) -> None:
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append(route_id)

    def create_route(
        self,
        flight_id: str,
        source_airport_code: str,
        source_country: str,
        destiny_airport_code: str,
        destiny_country: str,
        bag_cost: int,
        planned_start_date: datetime,
        planned_end_date: datetime,
    ) -> RouteInfo:
        route_id = str(uuid4())
        self.created.append(
            {
                "flightId": flight_id,
                "sourceAirportCode": source_airport_code,
                "sourceCountry": source_country,
                "destinyAirportCode": destiny_airport_code,
                "destinyCountry": destiny_country,
                "bagCost": bag_cost,
                "plannedStartDate": planned_start_date,
                "plannedEndDate": planned_end_date,
            }
        )
        self.created_ids.append(route_id)
        return RouteInfo(
            id=route_id,
            flightId=flight_id,
            plannedStartDate=planned_start_date,
            createdAt=datetime.now(timezone.utc),
        )


class FakePosts:
    """In-memory stand-in for the Posts service client."""

    def __init__(self, existing_posts: list[dict] | None = None):
        self.existing_posts = existing_posts or []
        self.created: list[dict] = []
        self.check_calls: list[tuple[str, str]] = []

    def has_post_for_route_and_owner(self, route_id: str, owner_id: str) -> bool:
        self.check_calls.append((route_id, owner_id))
        return any(
            p["routeId"] == route_id and p["userId"] == owner_id
            for p in self.existing_posts
        )

    def create_post(
        self, route_id: str, user_id: str, expire_at: datetime
    ) -> CreatedPost:
        post_id = str(uuid4())
        self.created.append(
            {
                "routeId": route_id,
                "userId": user_id,
                "expireAt": expire_at,
            }
        )
        return CreatedPost(
            id=post_id,
            userId=user_id,
            createdAt=datetime.now(timezone.utc),
        )


@pytest.fixture
def client():
    """HTTP client with fake Users/Routes/Posts dependencies (no real HTTP)."""
    fake_users = FakeUserValidation()
    fake_routes = FakeRoutes()
    fake_posts = FakePosts()

    app.dependency_overrides[get_validate_token_use_case] = (
        lambda: ValidateTokenUseCase(user_validation=fake_users)
    )
    app.dependency_overrides[get_create_post_use_case] = lambda: CreatePostUseCase(
        routes=fake_routes, posts=fake_posts
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        test_client.fake_users = fake_users
        test_client.fake_routes = fake_routes
        test_client.fake_posts = fake_posts
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def http_client(client):
    """Alias so router tests can request the client with a clear name."""
    return client
