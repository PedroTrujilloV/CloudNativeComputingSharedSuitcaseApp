"""Pytest fixtures for orchestrator tests."""

from dataclasses import dataclass
from typing import Any

import pytest

from domain.models import PostInfo
from domain.ports import PostsPort
from domain.ports.user_validation_port import (
    AuthenticatedUser,
    UserValidationPort,
)
from errors import (
    InvalidTokenError,
    PostNotFoundError,
    PostsServiceUnavailableError,
    TokenMissingError,
    UserNotOwnerError,
    UsersServiceUnavailableError,
)


@dataclass
class FakeUserValidation(UserValidationPort):
    """In-memory user validation stub for tests."""

    token_to_user: dict[str, AuthenticatedUser]
    missing_tokens: set[str]
    invalid_tokens: set[str]
    unreachable: bool = False

    def validate_token(self, token: str) -> AuthenticatedUser:
        if self.unreachable:
            raise UsersServiceUnavailableError(
                "The Users service is temporarily unavailable"
            )
        if token in self.missing_tokens:
            raise TokenMissingError("Missing bearer token")
        if token in self.invalid_tokens:
            raise InvalidTokenError("Invalid or expired token")
        if token not in self.token_to_user:
            raise InvalidTokenError("Invalid or expired token")
        return self.token_to_user[token]


@dataclass
class FakePosts(PostsPort):
    """In-memory posts stub for tests."""

    posts_by_id: dict[str, PostInfo]
    not_found: set[str]
    unreachable: bool = False

    def get_post(self, post_id: str) -> PostInfo:
        if self.unreachable:
            raise PostsServiceUnavailableError(
                "The Posts service is temporarily unavailable"
            )
        if post_id in self.not_found:
            raise PostNotFoundError(f"Post {post_id} does not exist")
        if post_id not in self.posts_by_id:
            raise PostNotFoundError(f"Post {post_id} does not exist")
        return self.posts_by_id[post_id]


@pytest.fixture
def fake_user_validation() -> FakeUserValidation:
    """Create a default FakeUserValidation for auth tests."""
    return FakeUserValidation(
        token_to_user={
            "valid_token": AuthenticatedUser(id="user1", username="alice")
        },
        missing_tokens=set(),
        invalid_tokens={"invalid_token"},
    )


@pytest.fixture
def fake_posts() -> FakePosts:
    """Create a default FakePosts for post lookup tests."""
    return FakePosts(
        posts_by_id={
            "post1": PostInfo(id="post1", userId="user1"),
            "post2": PostInfo(id="post2", userId="user2"),
        },
        not_found=set(),
    )
