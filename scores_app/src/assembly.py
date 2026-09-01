"""Dependency injection wiring for the Scores application."""

from entrypoints.api.deps import (
    get_count_scores_use_case,
    get_db_session,
    get_get_score_by_offer_use_case,
    get_get_score_use_case,
    get_reset_scores_use_case,
    get_score_repository,
    get_upsert_score_use_case,
)

__all__ = [
    "get_count_scores_use_case",
    "get_db_session",
    "get_get_score_by_offer_use_case",
    "get_get_score_use_case",
    "get_reset_scores_use_case",
    "get_score_repository",
    "get_upsert_score_use_case",
]
