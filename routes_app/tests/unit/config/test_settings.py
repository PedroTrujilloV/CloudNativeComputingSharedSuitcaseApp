"""Unit tests for Settings."""
import os
import pytest
from config import Settings


class TestSettingsAppName:
    """Tests for app_name setting."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Reset environment before each test."""
        monkeypatch.delenv("APP_NAME", raising=False)

    def test_app_name_default(self):
        """app_name should default to routes_app."""
        assert Settings.app_name() == "routes_app"

    def test_app_name_from_env(self, monkeypatch):
        """app_name should use value from APP_NAME env var."""
        monkeypatch.setenv("APP_NAME", "test_app")
        Settings.app_name.cache_clear()
        assert Settings.app_name() == "test_app"


class TestSettingsLogLevel:
    """Tests for log_level setting."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Reset environment before each test."""
        monkeypatch.delenv("LOG_LEVEL", raising=False)

    def test_log_level_default(self):
        """log_level should default to DEBUG."""
        assert Settings.log_level() == "DEBUG"

    def test_log_level_from_env(self, monkeypatch):
        """log_level should use value from LOG_LEVEL env var."""
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        Settings.log_level.cache_clear()
        assert Settings.log_level() == "INFO"


class TestSettingsDbDriver:
    """Tests for db_driver setting."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Reset environment before each test."""
        monkeypatch.delenv("DB_DRIVER", raising=False)

    def test_db_driver_default(self):
        """db_driver should default to postgresql."""
        assert Settings.db_driver() == "postgresql"

    def test_db_driver_from_env(self, monkeypatch):
        """db_driver should use value from DB_DRIVER env var."""
        monkeypatch.setenv("DB_DRIVER", "postgresql")
        assert Settings.db_driver() == "postgresql"

    def test_db_driver_case_insensitive(self, monkeypatch):
        """db_driver should be case-insensitive."""
        monkeypatch.setenv("DB_DRIVER", "PoStGrEsql")
        assert Settings.db_driver() == "postgresql"


class TestSettingsDbHost:
    """Tests for db_host setting."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Reset environment before each test."""
        monkeypatch.delenv("DB_HOST", raising=False)

    def test_db_host_default(self):
        """db_host should default to localhost."""
        assert Settings.db_host() == "localhost"

    def test_db_host_from_env(self, monkeypatch):
        """db_host should use value from DB_HOST env var."""
        monkeypatch.setenv("DB_HOST", "127.0.0.1")
        assert Settings.db_host() == "127.0.0.1"


class TestSettingsDbPort:
    """Tests for db_port setting."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Reset environment before each test."""
        monkeypatch.delenv("DB_PORT", raising=False)

    def test_db_port_default(self):
        """db_port should default to 5432."""
        assert Settings.db_port() == 5432

    def test_db_port_from_env(self, monkeypatch):
        """db_port should use value from DB_PORT env var."""
        monkeypatch.setenv("DB_PORT", "5433")
        assert Settings.db_port() == 5433


class TestSettingsDbName:
    """Tests for db_name setting."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Reset environment before each test."""
        monkeypatch.delenv("DB_NAME", raising=False)

    def test_db_name_default(self):
        """db_name should default to routes_db."""
        assert Settings.db_name() == "routes_db"

    def test_db_name_from_env(self, monkeypatch):
        """db_name should use value from DB_NAME env var."""
        monkeypatch.setenv("DB_NAME", "test_routes_db")
        assert Settings.db_name() == "test_routes_db"


class TestSettingsDbUser:
    """Tests for db_user setting."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Reset environment before each test."""
        monkeypatch.delenv("DB_USER", raising=False)

    def test_db_user_default(self):
        """db_user should default to routes_user."""
        assert Settings.db_user() == "routes_user"

    def test_db_user_from_env(self, monkeypatch):
        """db_user should use value from DB_USER env var."""
        monkeypatch.setenv("DB_USER", "test_user")
        assert Settings.db_user() == "test_user"


class TestSettingsDbPassword:
    """Tests for db_password setting."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Reset environment before each test."""
        monkeypatch.delenv("DB_PASSWORD", raising=False)

    def test_db_password_default_empty(self):
        """db_password should default to empty string."""
        assert Settings.db_password() == ""

    def test_db_password_from_env(self, monkeypatch):
        """db_password should use value from DB_PASSWORD env var."""
        monkeypatch.setenv("DB_PASSWORD", "secret123")
        assert Settings.db_password() == "secret123"


class TestSettingsDatabaseUrl:
    """Tests for database_url building."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Reset environment before each test."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("DB_DRIVER", raising=False)
        monkeypatch.delenv("SQLITE_URL", raising=False)
        monkeypatch.delenv("DB_USER", raising=False)
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)

    def test_database_url_default_postgresql(self, monkeypatch):
        """database_url should default to PostgreSQL when no DB_DRIVER."""
        url = Settings.database_url()
        assert url == "postgresql+psycopg://routes_user:@localhost:5432/routes_db"

    def test_database_url_default_sqlite(self, monkeypatch):
        """database_url should use SQLite when DB_DRIVER=sqlite."""
        monkeypatch.setenv("DB_DRIVER", "sqlite")
        url = Settings.database_url()
        assert url == "sqlite://"

    def test_database_url_from_explicit(self, monkeypatch):
        """database_url should use DATABASE_URL when explicitly set."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://custom:db@localhost/mydb")
        url = Settings.database_url()
        assert url == "postgresql://custom:db@localhost/mydb"

    def test_database_url_postgresql(self, monkeypatch):
        """database_url should build PostgreSQL URL when DB_DRIVER is postgresql."""
        monkeypatch.setenv("DB_DRIVER", "postgresql")
        monkeypatch.setenv("DB_USER", "testuser")
        monkeypatch.setenv("DB_PASSWORD", "testpass")
        monkeypatch.setenv("DB_HOST", "db.example.com")
        monkeypatch.setenv("DB_NAME", "testdb")
        url = Settings.database_url()
        assert "postgresql+psycopg://testuser:testpass@db.example.com:5432/testdb" in url

    def test_database_url_uses_sqlite_url_if_set(self, monkeypatch):
        """database_url should use SQLITE_URL when set."""
        monkeypatch.setenv("DB_DRIVER", "sqlite")
        monkeypatch.setenv("SQLITE_URL", "sqlite:///custom.db")
        url = Settings.database_url()
        assert url == "sqlite:///custom.db"