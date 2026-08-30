"""
Unit tests for database connection initialization.
"""
from sqlalchemy import create_engine, inspect

from adapters.database.connection import init_db
from config import Settings


class TestConnectionInitialization:
    """Tests for database connection and table creation."""

    def test_init_db_creates_engine(self):
        """Test that init_db creates database engine."""
        init_db()

    def test_init_db_creates_tables(self, tmp_path, monkeypatch):
        """Test that init_db creates all tables."""
        monkeypatch.setenv("SQLITE_URL", f"sqlite:///{tmp_path / 'tables.db'}")

        init_db()

        engine = create_engine(Settings.database_url())
        inspector = inspect(engine)

        assert "publications" in inspector.get_table_names()

    def test_init_db_publications_table_structure(self, tmp_path, monkeypatch):
        """Test publications table has correct columns."""
        monkeypatch.setenv("SQLITE_URL", f"sqlite:///{tmp_path / 'columns.db'}")

        init_db()

        engine = create_engine(Settings.database_url())
        inspector = inspect(engine)

        columns = {col["name"] for col in inspector.get_columns("publications")}

        assert "id" in columns
        assert "route_id" in columns
        assert "user_id" in columns
        assert "expire_at" in columns
        assert "created_at" in columns
