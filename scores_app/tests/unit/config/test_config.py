import os
from unittest.mock import patch

from config import Settings


def test_database_url_defaults_to_postgresql():
    """With no driver configured the service targets the shared Postgres instance."""
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


def test_database_url_uses_postgresql_when_driver_set():
    """PostgreSQL URL is built when DB_DRIVER=postgresql."""
    env = {
        "DB_DRIVER": "postgresql",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "scores_db",
        "DB_USER": "scores_user",
        "DB_PASSWORD": "secret",
    }
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("DATABASE_URL", None)
        url = Settings.database_url()

    assert url.startswith("postgresql+psycopg://")
    assert "scores_db" in url
    assert "scores_user" in url


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
    assert Settings.app_name == "scores_app"
