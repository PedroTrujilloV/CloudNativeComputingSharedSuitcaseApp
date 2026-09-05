"""Composition root for the RF-004 orchestrator.

Re-exports the dependency providers so the entrypoints can import them
from a single place.
"""

from entrypoints.api.deps import (
    get_create_offer_use_case,
    get_offer_preconditions_use_case,
    get_offers_service_client,
    get_posts_service_client,
    get_routes_service_client,
    get_scores_service_client,
    get_users_service_client,
    get_validate_token_use_case,
)

__all__ = [
    "get_create_offer_use_case",
    "get_offer_preconditions_use_case",
    "get_offers_service_client",
    "get_posts_service_client",
    "get_routes_service_client",
    "get_scores_service_client",
    "get_users_service_client",
    "get_validate_token_use_case",
]
