import os
from unittest.mock import patch

from config import Settings


def test_database_url_defaults_to_postgresql():
    """With no driver configured the service targets its own Postgres container."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DB_DRIVER", None)
        os.environ.pop("DATABASE_URL", None)
        url = Settings.database_url()

    assert url.startswith("postgresql+psycopg://")


def test_database_url_uses_sqlite_when_driver_set():
    """SQLite stays reachable for local runs and unit tests."""
    with patch.dict(os.environ, {"DB_DRIVER": "sqlite"}, clear=False):
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("SQLITE_URL", None)
        url = Settings.database_url()

    assert url.startswith("sqlite")
    assert url in {"sqlite://", "sqlite:///"} or ":memory:" in url


def test_database_url_uses_postgresql_when_driver_set():
    """PostgreSQL URL is built when DB_DRIVER=postgresql."""
    env = {
        "DB_DRIVER": "postgresql",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "users_db",
        "DB_USER": "users_user",
        "DB_PASSWORD": "secret",
    }
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("DATABASE_URL", None)
        url = Settings.database_url()

    assert url.startswith("postgresql+psycopg://")
    assert "users_db" in url
    assert "users_user" in url


def test_database_url_honors_explicit_database_url():
    """DATABASE_URL overrides driver-based construction."""
    with patch.dict(
        os.environ,
        {"DATABASE_URL": "postgresql+psycopg://u:p@db:5432/app"},
        clear=False,
    ):
        url = Settings.database_url()

    assert url == "postgresql+psycopg://u:p@db:5432/app"


def test_default_app_name():
    """Application name should come from environment or default."""
    assert Settings.app_name == "users_app"


def test_truenative_settings_defaults():
    """TrueNative settings fall back to the in-cluster deployment values."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("TRUE_NATIVE_BASE_URL", None)
        os.environ.pop("SECRET_TOKEN", None)
        os.environ.pop("USER_WEBHOOK_URL", None)
        assert Settings.truenative_base_url == "http://truenative-service"
        assert Settings.truenative_secret_token == ""
        assert Settings.user_webhook_url == (
            "http://user-verification-callback-service:8000/users/verify/callback"
        )


def test_truenative_settings_from_environment():
    """TrueNative settings can be overridden with environment variables."""
    env = {
        "TRUE_NATIVE_BASE_URL": "http://truenative.example:3000",
        "SECRET_TOKEN": "top-secret",
        "USER_WEBHOOK_URL": "http://callback.example/users/verify/callback",
    }
    with patch.dict(os.environ, env, clear=False):
        assert Settings.truenative_base_url == "http://truenative.example:3000"
        assert Settings.truenative_secret_token == "top-secret"
        assert (
            Settings.user_webhook_url == "http://callback.example/users/verify/callback"
        )
