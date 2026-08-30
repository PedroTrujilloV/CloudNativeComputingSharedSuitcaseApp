import os
from functools import lru_cache


class Settings:
    """Application settings loaded from environment variables."""

    @classmethod
    @property
    @lru_cache()
    def app_name(self) -> str:
        return os.getenv("APP_NAME", "users_app")

    @classmethod
    @property
    @lru_cache()
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "DEBUG")

    @classmethod
    @property
    def db_driver(self) -> str:
        """Persistence driver: postgresql (default) or sqlite (local only)."""
        return os.getenv("DB_DRIVER", "postgresql").lower()

    @classmethod
    @property
    def db_host(self) -> str:
        return os.getenv("DB_HOST", "localhost")

    @classmethod
    @property
    def db_port(self) -> int:
        return int(os.getenv("DB_PORT", "5432"))

    @classmethod
    @property
    def db_name(self) -> str:
        return os.getenv("DB_NAME", "users_db")

    @classmethod
    @property
    def db_user(self) -> str:
        return os.getenv("DB_USER", "users_user")

    @classmethod
    @property
    def db_password(self) -> str:
        return os.getenv("DB_PASSWORD", "")

    @classmethod
    def database_url(cls) -> str:
        """Build the SQLAlchemy URL.

        Defaults to PostgreSQL, which is what the deployment diagram gives the
        service: its own users-db container. SQLite stays available for local
        runs and unit tests through DB_DRIVER=sqlite, and DATABASE_URL
        overrides the driver-based construction entirely.
        """
        explicit = os.getenv("DATABASE_URL")
        if explicit:
            return explicit

        if cls.db_driver == "postgresql":
            return (
                f"postgresql+psycopg://{cls.db_user}:{cls.db_password}"
                f"@{cls.db_host}:{cls.db_port}/{cls.db_name}"
            )

        return os.getenv("SQLITE_URL", "sqlite://")
