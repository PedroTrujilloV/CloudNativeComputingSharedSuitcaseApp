"""
Database connection management for Posts Service.
"""

from adapters.database.models import Base
from config import Settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _engine_kwargs(url: str) -> dict:
    """SQLite needs StaticPool so an in-memory DB is shared across requests."""
    if url.startswith("sqlite"):
        return {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    return {"pool_pre_ping": True}


def build_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database URL."""
    url = database_url or Settings.database_url()
    return create_engine(url, echo=False, **_engine_kwargs(url))


def get_engine() -> Engine:
    """Return the process-wide engine (singleton), with its tables created.

    The schema is created once, when the engine is built, rather than on every
    repository instantiation: the engine is shared, so repeating it per request
    only costs a reflection round trip.
    """
    global _engine
    if _engine is None:
        engine = build_engine()
        _engine = engine
    return _engine


def build_session_factory(
    database_url: str | None = None,
) -> sessionmaker[Session]:
    """Create a session factory bound to an engine.

    When no explicit URL is provided, reuse the shared application engine.
    """
    if database_url is not None:
        engine = build_engine(database_url)
        return sessionmaker(bind=engine, autoflush=False, autocommit=False)

    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False
        )
    return _session_factory


def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory bound to the shared engine."""
    return build_session_factory()


def init_db(engine: Engine | None = None) -> None:
    """Create database tables if they do not exist."""
    active_engine = engine or get_engine()
    Base.metadata.create_all(bind=active_engine)


def check_connection(engine: Engine | None = None) -> bool:
    """Return True when the database accepts a simple connectivity probe."""
    active_engine = engine or get_engine()
    with active_engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def reset_engine_for_tests() -> None:
    """Drop the singleton engine and session factory (unit tests only)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
