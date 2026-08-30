import hashlib
import secrets


def generate_salt() -> str:
    """Generate a random salt for password hashing."""
    return secrets.token_hex(16)


def hash_password(plain_password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-HMAC-SHA256 and an explicit salt.

    Returns:
        Tuple of (password_hash, salt). Never returns the plaintext password.
    """
    if not plain_password:
        raise ValueError("Password cannot be empty")

    active_salt = salt or generate_salt()
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        active_salt.encode("utf-8"),
        120_000,
    )
    return digest.hex(), active_salt


def verify_password(plain_password: str, password_hash: str, salt: str) -> bool:
    """Return True when the plaintext password matches the stored hash."""
    candidate, _ = hash_password(plain_password, salt=salt)
    return secrets.compare_digest(candidate, password_hash)
