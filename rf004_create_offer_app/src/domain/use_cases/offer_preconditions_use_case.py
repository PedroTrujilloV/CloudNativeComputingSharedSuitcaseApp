"""Offer preconditions use case for RF-004.

Before the offer-creation stage may run, the referenced post must satisfy
the RF-004 preconditions (checked in the order documented by the sequence
diagram):

  1. The post must exist in the Posts service -> HTTP 404.
  2. The post must belong to a different user than the authenticated one
     (an owner cannot offer on their own post) -> HTTP 412.
  3. The post must not have expired yet (``expireAt`` in the future) ->
     HTTP 412.
"""

from datetime import datetime, timezone

from domain.models.post import PostInfo
from domain.ports.posts_port import PostsPort
from domain.ports.user_validation_port import AuthenticatedUser
from errors import OwnPostError, PostExpiredError


def _is_expired(expire_at: datetime, now: datetime) -> bool:
    """Return True when ``expire_at`` is not in the future (UTC-aware)."""
    if expire_at.tzinfo is None:
        expire_at = expire_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return expire_at <= now


class OfferPreconditionsUseCase:
    """Validate the post-level preconditions for creating an offer."""

    def __init__(self, posts: PostsPort):
        self.posts = posts

    def execute(self, *, user: AuthenticatedUser, post_id: str) -> PostInfo:
        """Fetch ``post_id`` and check the RF-004 preconditions for ``user``.

        Returns the post when every precondition holds, so the next stage
        can reuse it.

        Raises:
            PostNotFoundError: when the post does not exist (HTTP 404,
                empty body).
            OwnPostError: when the post belongs to the authenticated user
                (HTTP 412, empty body).
            PostExpiredError: when the post has already expired (HTTP 412,
                empty body).
            PostsServiceUnavailableError: when the Posts service cannot be
                reached (HTTP 503).
        """
        post = self.posts.get_post(post_id)

        if post.userId == user.id:
            raise OwnPostError("The post belongs to the authenticated user")

        if _is_expired(post.expireAt, datetime.now(timezone.utc)):
            raise PostExpiredError("The post has already expired")

        return post
