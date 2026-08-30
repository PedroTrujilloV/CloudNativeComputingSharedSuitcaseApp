"""
Pytest configuration and shared fixtures.
"""
import pytest
from fastapi.testclient import TestClient

from adapters.database.connection import reset_engine_for_tests
from adapters.database.repository import PublicationRepository
from entrypoints.api.main import app


@pytest.fixture(autouse=True)
def fresh_engine():
    """Give every test its own database.

    The application engine is a process-wide singleton, so it is dropped before
    and after each test. Dropping the engine is enough to isolate tests against
    in-memory SQLite (a new engine means a new, empty database), but it does
    nothing against a real server like PostgreSQL, where rows persist across
    tests and across pytest invocations, so data is also wiped explicitly.

    The wipe happens in teardown, not setup: building a repository eagerly in
    setup would force the engine to be created before the test gets a chance
    to monkeypatch SQLITE_URL/DB_* first (tests that point the engine somewhere
    custom, e.g. the connection tests, rely on the engine staying unbuilt until
    they are ready).
    """
    reset_engine_for_tests()
    yield
    PublicationRepository().delete_all()
    reset_engine_for_tests()


@pytest.fixture
def client():
    """Provide a test client for the FastAPI application."""
    return TestClient(app)
