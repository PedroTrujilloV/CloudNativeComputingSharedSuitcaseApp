import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from adapters.database.models import Base
from config import Settings

logger = logging.getLogger(__name__)

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
    return create_engine(url, **_engine_kwargs(url))


def get_engine() -> Engine:
    """Return the process-wide engine (singleton)."""
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def build_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
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


def ensure_schema_columns(engine: Engine | None = None) -> None:
    """Add the nullable columns that a persistent database is missing.

    ``create_all`` builds missing tables but does not evolve the ones that
    already exist, so a database that survived an earlier deployment of the
    application (for example a persistent RDS instance) keeps its old column
    set and every ORM query fails on the first missing column. This routine
    inspects every mapped table and adds the nullable columns the model
    expects. A missing primary key or non nullable column cannot be added
    safely to a table that already holds rows, so the routine raises for
    them instead of guessing.
    """
    active_engine = engine or get_engine()
    inspector = inspect(active_engine)
    dialect = active_engine.dialect
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all already built it with the full schema
        database_columns = {
            column["name"] for column in inspector.get_columns(table.name)
        }
        for column in table.columns:
            if column.name in database_columns:
                continue
            if column.primary_key or not column.nullable:
                raise RuntimeError(
                    f"Missing non optional column {column.name} of table "
                    f"{table.name}; it cannot be added to an existing table "
                    "without a data migration"
                )
            type_sql = column.type.compile(dialect=dialect)
            with active_engine.begin() as connection:
                connection.execute(
                    text(
                        f'ALTER TABLE "{table.name}" '
                        f'ADD COLUMN "{column.name}" {type_sql} NULL'
                    )
                )
            logger.info(
                "Added the missing column %s.%s (%s) to the existing database",
                table.name,
                column.name,
                type_sql,
            )


def init_db(engine: Engine | None = None) -> None:
    """Create database tables if they do not exist and evolve missing columns."""
    active_engine = engine or get_engine()
    Base.metadata.create_all(bind=active_engine)
    ensure_schema_columns(active_engine)


def check_connection(engine: Engine | None = None) -> bool:
    """Return True when the database accepts a simple connectivity probe."""
    active_engine = engine or get_engine()
    with active_engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def reset_engine_for_tests() -> None:
    """Drop the singleton engine/session factory (unit tests only)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
