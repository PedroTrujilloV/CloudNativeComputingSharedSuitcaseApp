"""
Database connection management for Posts Service.
"""
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from config import Settings
from adapters.database.models import Base

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
        Base.metadata.create_all(engine)
        _engine = engine
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory bound to the shared engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine())
    return _session_factory


def init_db():
    """Initialize database connection and create tables."""
    get_engine()


def reset_engine_for_tests() -> None:
    """Drop the singleton engine and session factory (unit tests only)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
