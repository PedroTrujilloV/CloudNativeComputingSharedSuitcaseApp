"""Unit tests for the OfferPreconditionsUseCase (post-level preconditions)."""

from datetime import datetime, timedelta, timezone

import pytest

from domain.models.post import PostInfo
from domain.ports.user_validation_port import AuthenticatedUser
from domain.use_cases.offer_preconditions_use_case import OfferPreconditionsUseCase
from errors import (
    OwnPostError,
    PostExpiredError,
    PostNotFoundError,
    PostsServiceUnavailableError,
)

USER = AuthenticatedUser(id="user-1", username="tester")


class FakePosts:
    """In-memory stand-in for the Posts port."""

    def __init__(self, post: PostInfo | None = None, error: Exception | None = None):
        self.post = post
        self.error = error
        self.get_calls: list[str] = []

    def get_post(self, post_id: str) -> PostInfo:
        self.get_calls.append(post_id)
        if self.error is not None:
            raise self.error
        if self.post is None:
            raise PostNotFoundError(f"Post {post_id} does not exist")
        return self.post


def _post(user_id: str = "owner-1", expire_in: timedelta = timedelta(days=1)):
    return PostInfo(
        id="post-1",
        routeId="route-1",
        userId=user_id,
        expireAt=datetime.now(timezone.utc) + expire_in,
    )


def test_unknown_post_raises_not_found():
    """A post the Posts service does not know about is a 404 error."""
    use_case = OfferPreconditionsUseCase(posts=FakePosts(post=None))

    with pytest.raises(PostNotFoundError):
        use_case.execute(user=USER, post_id="missing")


def test_posts_service_unavailable_propagates():
    """A Posts outage propagates as PostsServiceUnavailableError (503)."""
    use_case = OfferPreconditionsUseCase(
        posts=FakePosts(error=PostsServiceUnavailableError("down"))
    )

    with pytest.raises(PostsServiceUnavailableError):
        use_case.execute(user=USER, post_id="post-1")


def test_own_post_raises_own_post_error():
    """A post owned by the caller is rejected (412) before the expiry check."""
    post = _post(user_id="user-1")
    use_case = OfferPreconditionsUseCase(posts=FakePosts(post=post))

    with pytest.raises(OwnPostError):
        use_case.execute(user=USER, post_id="post-1")


def test_expired_post_raises_expired_error():
    """A post whose expireAt is in the past is rejected (412)."""
    post = _post(expire_in=timedelta(seconds=-10))
    use_case = OfferPreconditionsUseCase(posts=FakePosts(post=post))

    with pytest.raises(PostExpiredError):
        use_case.execute(user=USER, post_id="post-1")


def test_naive_expire_at_is_treated_as_utc():
    """A naive expireAt (no tzinfo) is assumed to be UTC and still checked."""
    post = PostInfo(
        id="post-1",
        routeId="route-1",
        userId="owner-1",
        expireAt=datetime.now(timezone.utc).replace(tzinfo=None)
        - timedelta(seconds=10),
    )
    use_case = OfferPreconditionsUseCase(posts=FakePosts(post=post))

    with pytest.raises(PostExpiredError):
        use_case.execute(user=USER, post_id="post-1")


def test_own_post_wins_over_expiry():
    """Own-post (412) is checked before expiry (412), per the sequence diagram."""
    post = _post(user_id="user-1", expire_in=timedelta(seconds=-10))
    use_case = OfferPreconditionsUseCase(posts=FakePosts(post=post))

    with pytest.raises(OwnPostError):
        use_case.execute(user=USER, post_id="post-1")


def test_valid_post_is_returned():
    """A post owned by another user and not expired passes the gate."""
    post = _post()
    use_case = OfferPreconditionsUseCase(posts=FakePosts(post=post))

    result = use_case.execute(user=USER, post_id="post-1")

    assert result is post
    assert use_case.posts.get_calls == ["post-1"]
