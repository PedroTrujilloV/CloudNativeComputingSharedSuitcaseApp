"""Ownership gate use case for RF-005.

Before any data aggregation may run, the referenced post must satisfy
the RF-005 preconditions:

  1. The post must exist in the Posts service (HTTP 404).
  2. The post must belong to the authenticated user (HTTP 403).
"""

from domain.models import PostInfo
from domain.ports import PostsPort
from domain.ports.user_validation_port import AuthenticatedUser
from errors import PostNotFoundError, UserNotOwnerError


class OwnershipGateUseCase:
    """Validate the post-level ownership check for RF-005."""

    def __init__(self, posts: PostsPort):
        self.posts = posts

    def execute(self, *, user: AuthenticatedUser, post_id: str) -> PostInfo:
        """Fetch `post_id` and check the RF-005 ownership for `user`.

        Returns the post when every precondition holds, so the next stage
        can reuse it.

        Raises:
            PostNotFoundError: when the post does not exist (HTTP 404,
                empty body).
            UserNotOwnerError: when the post does not belong to the
                authenticated user (HTTP 403, empty body).
            PostsServiceUnavailableError: when the Posts service cannot be
                reached (HTTP 503).
        """
        post = self.posts.get_post(post_id)

        if post.userId != user.id:
            raise UserNotOwnerError("The post does not belong to the authenticated user")

        return post
