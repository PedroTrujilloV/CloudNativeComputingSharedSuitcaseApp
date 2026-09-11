"""Test suite for OwnershipGateUseCase."""

import pytest

from domain.models import PostInfo
from domain.ports.user_validation_port import AuthenticatedUser
from domain.use_cases.ownership_gate_use_case import OwnershipGateUseCase
from errors import (
    PostNotFoundError,
    PostsServiceUnavailableError,
    UserNotOwnerError,
)
from tests.conftest import FakePosts


def test_ownership_gate_with_owner():
    """Executing when user is the post owner succeeds."""
    user = AuthenticatedUser(id="user1", username="alice")
    post = PostInfo(id="post1", userId="user1")
    fake = FakePosts(
        posts_by_id={"post1": post},
        not_found=set(),
    )
    use_case = OwnershipGateUseCase(posts=fake)
    use_case.execute(user=user, post_id="post1")


def test_ownership_gate_with_non_owner():
    """Executing when user is not the post owner raises UserNotOwnerError."""
    user = AuthenticatedUser(id="user1", username="alice")
    post = PostInfo(id="post1", userId="user2")
    fake = FakePosts(
        posts_by_id={"post1": post},
        not_found=set(),
    )
    use_case = OwnershipGateUseCase(posts=fake)
    with pytest.raises(UserNotOwnerError):
        use_case.execute(user=user, post_id="post1")


def test_ownership_gate_with_nonexistent_post():
    """Executing with a non-existent post id raises PostNotFoundError."""
    user = AuthenticatedUser(id="user1", username="alice")
    fake = FakePosts(
        posts_by_id={},
        not_found={"nonexistent"},
    )
    use_case = OwnershipGateUseCase(posts=fake)
    with pytest.raises(PostNotFoundError):
        use_case.execute(user=user, post_id="nonexistent")


def test_ownership_gate_when_posts_service_unavailable():
    """Executing when Posts service is down raises PostsServiceUnavailableError."""
    user = AuthenticatedUser(id="user1", username="alice")
    fake = FakePosts(
        posts_by_id={},
        not_found=set(),
        unreachable=True,
    )
    use_case = OwnershipGateUseCase(posts=fake)
    with pytest.raises(PostsServiceUnavailableError):
        use_case.execute(user=user, post_id="post1")
