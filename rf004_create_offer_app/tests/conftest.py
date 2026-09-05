"""Test helpers for the RF-004 orchestrator."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from domain.models.post import PostInfo
from domain.ports.user_validation_port import AuthenticatedUser
from domain.use_cases.offer_preconditions_use_case import OfferPreconditionsUseCase
from domain.use_cases.validate_token_use_case import ValidateTokenUseCase
from entrypoints.api.deps import (
    get_offer_preconditions_use_case,
    get_validate_token_use_case,
)
from entrypoints.api.main import app


def valid_payload(**overrides) -> dict:
    """A well-formed RF-004 request body."""
    payload = {
        "description": "Space for one medium bag",
        "size": "MEDIUM",
        "fragile": False,
        "offer": 50000,
    }
    payload.update(overrides)
    return payload


def valid_post(**overrides) -> PostInfo:
    """A post owned by ``owner_id`` that has not expired yet."""
    post = {
        "id": str(uuid4()),
        "routeId": "route-1",
        "userId": "owner-1",
        "expireAt": datetime.now(timezone.utc).replace(year=2099, tzinfo=timezone.utc),
    }
    post.update(overrides)
    return PostInfo(**post)


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


class FakePosts:
    """In-memory stand-in for the Posts service client."""

    def __init__(self, posts: dict[str, PostInfo] | None = None):
        self.posts = posts or {}
        self.get_calls: list[str] = []

    def get_post(self, post_id: str) -> PostInfo:
        self.get_calls.append(post_id)
        post = self.posts.get(post_id)
        if post is None:
            from errors import PostNotFoundError

            raise PostNotFoundError(f"Post {post_id} does not exist")
        return post


@pytest.fixture
def client():
    """HTTP client with fake Users/Posts dependencies (no real HTTP)."""
    fake_users = FakeUserValidation()
    fake_posts = FakePosts()

    app.dependency_overrides[get_validate_token_use_case] = (
        lambda: ValidateTokenUseCase(user_validation=fake_users)
    )
    app.dependency_overrides[get_offer_preconditions_use_case] = (
        lambda: OfferPreconditionsUseCase(posts=fake_posts)
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        test_client.fake_users = fake_users
        test_client.fake_posts = fake_posts
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def http_client(client):
    """Alias so router tests can request the client with a clear name."""
    return client
