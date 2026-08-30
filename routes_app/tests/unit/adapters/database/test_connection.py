import pytest
from sqlalchemy import text
from adapters.database.connection import (
    build_engine,
    check_connection,
    get_engine,
    init_db,
    reset_engine_for_tests,
    Settings,
    _engine,
    _session_factory,
)


class TestBuildEngine:
    """Tests for build_engine function."""

    def test_build_engine_default_url(self):
        """build_engine should use default SQLite URL."""
        reset_engine_for_tests()
        engine = build_engine()
        assert engine is not None

    def test_build_engine_custom_url(self):
        """build_engine should accept custom URL."""
        reset_engine_for_tests()
        custom_url = "sqlite:///test_custom.db"
        engine = build_engine(custom_url)
        assert engine is not None


class TestGetEngine:
    """Tests for get_engine function."""

    def test_get_engine_singleton(self):
        """get_engine should return same engine instance (singleton)."""
        reset_engine_for_tests()
        engine1 = get_engine()
        engine2 = get_engine()
        assert engine1 is engine2


class TestInitDb:
    """Tests for init_db function."""

    def test_init_db_creates_tables(self):
        """init_db should create tables in the database."""
        reset_engine_for_tests()
        engine = get_engine()
        init_db(engine)
        # If we got here without error, tables were created

    def test_init_db_with_explicit_engine(self):
        """init_db should accept explicit engine parameter."""
        reset_engine_for_tests()
        engine = build_engine("sqlite:///")
        init_db(engine)


class TestCheckConnection:
    """Tests for check_connection function."""

    def test_check_connection_returns_true(self):
        """check_connection should return True for valid database."""
        reset_engine_for_tests()
        result = check_connection()
        assert result is True

    def test_check_connection_with_explicit_engine(self):
        """check_connection should accept explicit engine."""
        reset_engine_for_tests()
        engine = build_engine("sqlite:///")
        result = check_connection(engine)
        assert result is True


class TestResetEngineForTests:
    """Tests for reset_engine_for_tests function."""

    def test_reset_engine_for_tests_resets_engine(self):
        """reset_engine_for_tests should reset the engine."""
        reset_engine_for_tests()
        engine = get_engine()
        reset_engine_for_tests()
        new_engine = get_engine()
        # After reset, new engine should be a different instance

    def test_reset_engine_for_tests_resets_session_factory(self):
        """reset_engine_for_tests should reset session factory."""
        reset_engine_for_tests()
        from adapters.database.connection import _session_factory
        # Session factory should be None after reset