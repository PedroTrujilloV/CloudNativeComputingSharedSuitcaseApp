"""
Application configuration module.
Loads settings from environment variables.
"""

from os import getenv


class Settings:
    """Application settings loaded from environment variables."""

    @classmethod
    @property
    def app_name(cls) -> str:
        """Application name from APP_NAME env var."""
        return getenv("APP_NAME", "offers_app")

    @classmethod
    @property
    def log_level(cls) -> str:
        """Logging level from LOG_LEVEL env var."""
        return getenv("LOG_LEVEL", "INFO")

    @classmethod
    @property
    def db_driver(cls) -> str:
        """Database driver from DB_DRIVER env var (sqlite or postgresql)."""
        return getenv("DB_DRIVER", "postgresql").lower()

    @classmethod
    @property
    def db_host(cls) -> str:
        """Database host from DB_HOST env var."""
        return getenv("DB_HOST", "localhost")

    @classmethod
    @property
    def db_port(cls) -> int:
        """Database port from DB_PORT env var."""
        return int(getenv("DB_PORT", "5432"))

    @classmethod
    @property
    def db_name(cls) -> str:
        """Database name from DB_NAME env var."""
        return getenv("DB_NAME", "offers_db")

    @classmethod
    @property
    def db_user(cls) -> str:
        """Database user from DB_USER env var."""
        return getenv("DB_USER", "offers_user")

    @classmethod
    @property
    def db_password(cls) -> str:
        """Database password from DB_PASSWORD env var."""
        return getenv("DB_PASSWORD", "")

    @classmethod
    def database_url(cls) -> str:
        """Construct database URL based on configuration."""
        # Check for explicit DATABASE_URL first
        explicit_url = getenv("DATABASE_URL")
        if explicit_url:
            return explicit_url

        # Otherwise, build from components
        driver = cls.db_driver

        if driver == "sqlite":
            sqlite_url = getenv("SQLITE_URL", "sqlite://")
            return sqlite_url

        # PostgreSQL
        user = cls.db_user
        password = cls.db_password
        host = cls.db_host
        port = cls.db_port
        name = cls.db_name

        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"
