import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from adapters.database.models import Base
from entrypoints.api.deps import get_db_session
from entrypoints.api.main import app


@pytest.fixture
def client():
    """HTTP client with an isolated in-memory SQLite database."""
    # Force SQLite for unit tests before TestClient starts the lifespan.
    # pyproject.toml's env=[] does NOT set env vars at runtime; pytest-env plugin
    # is required for that.  Without this override the default DB_DRIVER is
    # "postgresql" and init_db() in the lifespan will fail because no PG server
    # is available.
    os.environ["DB_DRIVER"] = "sqlite"

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False
    )

    def override_get_db_session():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()