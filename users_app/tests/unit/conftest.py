import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from adapters.database.models import Base
from domain.ports.truenative_port import TrueNativeVerificationPort
from entrypoints.api import deps
from entrypoints.api.deps import get_db_session
from entrypoints.api.main import app


class FakeVerificationProvider(TrueNativeVerificationPort):
    """In-memory stand-in for the TrueNative verification provider.

    Records every request so tests can assert on the user data, the user
    identifier, and the transaction identifier that were sent. When an error
    is assigned, the provider raises it on the next request to simulate a
    TrueNative rejection (TrueNativeRequestError) or an unreachable platform
    (TrueNativeUnreachableError).
    """

    def __init__(self) -> None:
        self.calls = []
        self.error = None

    def request_verification(
        self,
        *,
        user,
        user_identifier: str,
        transaction_identifier: str,
    ) -> str:
        self.calls.append(
            {
                "user": user,
                "user_identifier": user_identifier,
                "transaction_identifier": transaction_identifier,
            }
        )
        if self.error is not None:
            raise self.error
        return f"ruv-{transaction_identifier}"


@pytest.fixture
def verification_provider(monkeypatch):
    """Provider used by the create user flow, with its calls recorded."""
    provider = FakeVerificationProvider()
    monkeypatch.setattr(deps, "get_truenative_verification_provider", lambda: provider)
    return provider


@pytest.fixture
def db_session_factory():
    """Session factory bound to a fresh in-memory SQLite database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    engine.dispose()


@pytest.fixture
def db_session(db_session_factory):
    """Session for tests that inspect what the API stored in the database."""
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(verification_provider, db_session_factory):
    """HTTP client with an isolated in-memory SQLite database and a fake TrueNative provider."""

    def override_get_db_session():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
