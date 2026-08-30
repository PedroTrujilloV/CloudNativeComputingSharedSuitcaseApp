import os
from functools import lru_cache


class Settings:
    """Application settings loaded from environment variables."""

    @classmethod
    @lru_cache()
    def app_name(cls) -> str:
        return os.getenv("APP_NAME", "routes_app")

    @classmethod
    @lru_cache()
    def log_level(cls) -> str:
        return os.getenv("LOG_LEVEL", "DEBUG")

    @classmethod
    def db_driver(cls) -> str:
        """Persistence driver: postgresql (production) or sqlite (local dev)."""
        return os.getenv("DB_DRIVER", "postgresql").lower()

    @classmethod
    def db_host(cls) -> str:
        return os.getenv("DB_HOST", "localhost")

    @classmethod
    def db_port(cls) -> int:
        return int(os.getenv("DB_PORT", "5432"))

    @classmethod
    def db_name(cls) -> str:
        return os.getenv("DB_NAME", "routes_db")

    @classmethod
    def db_user(cls) -> str:
        return os.getenv("DB_USER", "routes_user")

    @classmethod
    def db_password(cls) -> str:
        return os.getenv("DB_PASSWORD", "")

    @classmethod
    def database_url(cls) -> str:
        """Build the SQLAlchemy URL.

        Production default is PostgreSQL (`postgresql+psycopg://`).
        Local development can override with `DB_DRIVER=sqlite`.
        `DATABASE_URL` always takes precedence over `DB_DRIVER`.
        """
        explicit = os.getenv("DATABASE_URL")
        if explicit:
            return explicit

        if cls.db_driver() == "postgresql":
            return (
                f"postgresql+psycopg://{cls.db_user()}:{cls.db_password()}"
                f"@{cls.db_host()}:{cls.db_port()}/{cls.db_name()}"
            )

        return os.getenv("SQLITE_URL", "sqlite://")