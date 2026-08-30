"""Dependency injection wiring for the Offers application."""

from entrypoints.api.deps import (
    get_create_offer_use_case,
    get_db_session,
    get_delete_all_offers_use_case,
    get_offer_repository,
)

__all__ = [
    "get_create_offer_use_case",
    "get_db_session",
    "get_delete_all_offers_use_case",
    "get_offer_repository",
]