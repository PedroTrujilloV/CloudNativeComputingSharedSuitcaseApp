"""
Unit tests for application configuration.
Tests all Settings properties and database URL construction.
"""
from config import Settings


class TestSettingsProperties:
    """Tests for Settings class properties."""

    def test_app_name_default(self):
        """Test default app name."""
        assert Settings.app_name == "posts_app"

    def test_app_name_from_env(self, monkeypatch):
        """Test app name from environment variable."""
        monkeypatch.setenv("APP_NAME", "custom-posts-app")
        assert Settings.app_name == "custom-posts-app"

    def test_log_level_default(self):
        """Test default log level."""
        assert Settings.log_level == "INFO"

    def test_log_level_from_env(self, monkeypatch):
        """Test log level from environment variable."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        assert Settings.log_level == "DEBUG"

    def test_db_driver_default(self):
        """Test default database driver."""
        # pytest-env pins DB_DRIVER=sqlite for the test suite; the app's real
        # default is postgresql (see config.py).
        assert Settings.db_driver == "sqlite"

    def test_db_driver_postgresql(self, monkeypatch):
        """Test PostgreSQL database driver."""
        monkeypatch.setenv("DB_DRIVER", "postgresql")
        assert Settings.db_driver == "postgresql"

    def test_db_host_default(self):
        """Test default database host."""
        assert Settings.db_host == "localhost"

    def test_db_host_from_env(self, monkeypatch):
        """Test database host from environment."""
        monkeypatch.setenv("DB_HOST", "db.example.com")
        assert Settings.db_host == "db.example.com"

    def test_db_port_default(self):
        """Test default database port."""
        assert Settings.db_port == 5432

    def test_db_port_from_env(self, monkeypatch):
        """Test database port from environment."""
        monkeypatch.setenv("DB_PORT", "5433")
        assert Settings.db_port == 5433

    def test_db_name_default(self):
        """Test default database name."""
        assert Settings.db_name == "posts_db"

    def test_db_name_from_env(self, monkeypatch):
        """Test database name from environment."""
        monkeypatch.setenv("DB_NAME", "custom_db")
        assert Settings.db_name == "custom_db"

    def test_db_user_default(self):
        """Test default database user."""
        assert Settings.db_user == "posts_user"

    def test_db_user_from_env(self, monkeypatch):
        """Test database user from environment."""
        monkeypatch.setenv("DB_USER", "postgres")
        assert Settings.db_user == "postgres"

    def test_db_password_default(self, monkeypatch):
        """Test default database password."""
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        assert Settings.db_password == ""

    def test_db_password_from_env(self, monkeypatch):
        """Test database password from environment."""
        monkeypatch.setenv("DB_PASSWORD", "secret123")
        assert Settings.db_password == "secret123"


class TestDatabaseUrl:
    """Tests for database URL construction."""

    def test_database_url_explicit(self, monkeypatch):
        """Test explicit DATABASE_URL env var takes precedence."""
        explicit_url = "postgresql+psycopg://user:pass@host:5432/db"
        monkeypatch.setenv("DATABASE_URL", explicit_url)

        assert Settings.database_url() == explicit_url

    def test_database_url_sqlite_default(self, monkeypatch):
        """Test default SQLite URL."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_DRIVER", "sqlite")

        url = Settings.database_url()

        assert url == "sqlite://"

    def test_database_url_sqlite_custom(self, monkeypatch):
        """Test custom SQLite URL."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_DRIVER", "sqlite")
        monkeypatch.setenv("SQLITE_URL", "sqlite:///custom.db")

        url = Settings.database_url()

        assert url == "sqlite:///custom.db"

    def test_database_url_postgresql(self, monkeypatch):
        """Test PostgreSQL URL construction."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_DRIVER", "postgresql")
        monkeypatch.setenv("DB_USER", "postgres")
        monkeypatch.setenv("DB_PASSWORD", "secret")
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "posts_db")

        url = Settings.database_url()

        assert url == "postgresql+psycopg://postgres:secret@localhost:5432/posts_db"

    def test_database_url_postgresql_custom_port(self, monkeypatch):
        """Test PostgreSQL URL with custom port."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_DRIVER", "postgresql")
        monkeypatch.setenv("DB_USER", "user")
        monkeypatch.setenv("DB_PASSWORD", "pass")
        monkeypatch.setenv("DB_HOST", "db.example.com")
        monkeypatch.setenv("DB_PORT", "5433")
        monkeypatch.setenv("DB_NAME", "custom_db")

        url = Settings.database_url()

        assert url == "postgresql+psycopg://user:pass@db.example.com:5433/custom_db"
