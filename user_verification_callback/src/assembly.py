"""Dependency injection wiring for the user verification callback receiver."""

from entrypoints.api.deps import (
    get_email_notification,
    get_process_verification_callback_use_case,
    get_users_service_client,
)

__all__ = [
    "get_email_notification",
    "get_process_verification_callback_use_case",
    "get_users_service_client",
]
