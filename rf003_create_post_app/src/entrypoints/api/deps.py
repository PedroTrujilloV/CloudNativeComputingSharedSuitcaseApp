"""Dependency providers for the RF-003 orchestrator."""

from fastapi import Depends

from adapters.http.posts_service_client import PostsServiceClient
from adapters.http.routes_service_client import RoutesServiceClient
from adapters.http.users_service_client import UsersServiceClient
from domain.ports.posts_port import PostsPort
from domain.ports.routes_port import RoutesPort
from domain.ports.user_validation_port import UserValidationPort
from domain.use_cases.create_post_use_case import CreatePostUseCase
from domain.use_cases.validate_token_use_case import ValidateTokenUseCase


def get_users_service_client():
    """Yield a request-scoped client for the Users service.

    A fresh ``httpx.Client`` is created per request and always closed, so no
    connection state leaks between requests.
    """
    client = UsersServiceClient()
    try:
        yield client
    finally:
        client.close()


def get_routes_service_client():
    """Yield a request-scoped client for the Routes service."""
    client = RoutesServiceClient()
    try:
        yield client
    finally:
        client.close()


def get_posts_service_client():
    """Yield a request-scoped client for the Posts service."""
    client = PostsServiceClient()
    try:
        yield client
    finally:
        client.close()


def get_validate_token_use_case(
    user_validation: UserValidationPort = Depends(get_users_service_client),
) -> ValidateTokenUseCase:
    """Build the authentication gate use case."""
    return ValidateTokenUseCase(user_validation=user_validation)


def get_create_post_use_case(
    routes: RoutesPort = Depends(get_routes_service_client),
    posts: PostsPort = Depends(get_posts_service_client),
) -> CreatePostUseCase:
    """Build the core orchestration use case (route + post creation)."""
    return CreatePostUseCase(routes=routes, posts=posts)
