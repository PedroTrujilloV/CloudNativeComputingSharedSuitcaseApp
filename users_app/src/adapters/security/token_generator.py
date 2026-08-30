import secrets
from datetime import datetime, timedelta, timezone


def generate_opaque_token() -> str:
    """Generate a random opaque token (not a JWT)."""
    return secrets.token_urlsafe(32)


def build_expire_at(ttl_minutes: int = 60) -> datetime:
    """Return a naive UTC expiration timestamp."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        minutes=ttl_minutes
    )
