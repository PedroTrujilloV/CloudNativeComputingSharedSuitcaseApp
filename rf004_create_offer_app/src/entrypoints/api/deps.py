"""Dependency providers for the RF-004 orchestrator."""

from fastapi import Depends

from adapters.http.offers_service_client import OffersServiceClient
from adapters.http.posts_service_client import PostsServiceClient
from adapters.http.routes_service_client import RoutesServiceClient
from adapters.http.scores_service_client import ScoresServiceClient
from adapters.http.users_service_client import UsersServiceClient
from domain.ports.offers_port import OffersPort
from domain.ports.posts_port import PostsPort
from domain.ports.routes_port import RoutesPort
from domain.ports.scores_port import ScoresPort
from domain.ports.user_validation_port import UserValidationPort
from domain.use_cases.create_offer_use_case import CreateOfferUseCase
from domain.use_cases.offer_preconditions_use_case import OfferPreconditionsUseCase
from domain.use_cases.validate_token_use_case import ValidateTokenUseCase


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
    """Yield a request-scoped client for the Scores service."""
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


def get_offer_preconditions_use_case(
    posts: PostsPort = Depends(get_posts_service_client),
) -> OfferPreconditionsUseCase:
    """Build the post preconditions use case (post lookup + checks)."""
    return OfferPreconditionsUseCase(posts=posts)


def get_create_offer_use_case(
    offers: OffersPort = Depends(get_offers_service_client),
    routes: RoutesPort | None = Depends(get_routes_service_client),
    scores: ScoresPort | None = Depends(get_scores_service_client),
) -> CreateOfferUseCase:
    """Build the create offer use case."""
    return CreateOfferUseCase(offers=offers, routes=routes, scores=scores)
