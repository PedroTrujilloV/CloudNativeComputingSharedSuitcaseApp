"""Dependency providers for the RF-005 orchestrator."""

from fastapi import Depends

from adapters.http.offers_service_client import OffersServiceClient
from adapters.http.posts_service_client import PostsServiceClient
from adapters.http.routes_service_client import RoutesServiceClient
from adapters.http.scores_service_client import ScoresServiceClient
from adapters.http.users_service_client import UsersServiceClient
from domain.ports import PostsPort
from domain.ports.offers_port import OffersPort
from domain.ports.routes_port import RoutesPort
from domain.ports.scores_port import ScoresPort
from domain.ports.user_validation_port import UserValidationPort
from domain.use_cases import ValidateTokenUseCase
from domain.use_cases.ownership_gate_use_case import OwnershipGateUseCase
from domain.use_cases.query_post_use_case import QueryPostUseCase


def get_users_service_client():
    """Yield a request-scoped client for the Users service."""
    client = UsersServiceClient()
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


def get_routes_service_client():
    """Yield a request-scoped client for the Routes service."""
    client = RoutesServiceClient()
    try:
        yield client
    finally:
        client.close()


def get_offers_service_client():
    """Yield a request-scoped client for the Offers service."""
    client = OffersServiceClient()
    try:
        yield client
    finally:
        client.close()


def get_scores_service_client():
    """Yield a request-scoped client for the Score service."""
    client = ScoresServiceClient()
    try:
        yield client
    finally:
        client.close()


def get_validate_token_use_case(
    user_validation: UserValidationPort = Depends(get_users_service_client),
) -> ValidateTokenUseCase:
    """Build the authentication gate use case."""
    return ValidateTokenUseCase(user_validation=user_validation)


def get_ownership_gate_use_case(
    posts: PostsPort = Depends(get_posts_service_client),
) -> OwnershipGateUseCase:
    """Build the ownership gate use case (post lookup + owner check)."""
    return OwnershipGateUseCase(posts=posts)


def get_query_post_use_case(
    routes: RoutesPort = Depends(get_routes_service_client),
    offers: OffersPort = Depends(get_offers_service_client),
    scores: ScoresPort = Depends(get_scores_service_client),
) -> QueryPostUseCase:
    """Build the aggregation use case."""
    return QueryPostUseCase(routes=routes, offers=offers, scores=scores)

