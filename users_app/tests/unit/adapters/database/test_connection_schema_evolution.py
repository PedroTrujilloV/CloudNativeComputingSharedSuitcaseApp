"""Startup evolution of a persistent database that predates the model.

``create_all`` only builds missing tables. A database that survived an
earlier deployment of the application keeps its old column set, so the
startup routine must add the nullable columns the model expects. These
tests build a stale ``users`` table with explicit DDL (the schema of a
deployment from before the ``ruv`` and ``expireAt`` columns) and check the
behavior of ``init_db`` on top of it.
"""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from adapters.database.connection import init_db
from adapters.database.models import Base, UserModel

# Schema of the users table from a deployment that predates ruv/expireAt.
STALE_USERS_DDL = """
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    "phoneNumber" VARCHAR(50),
    dni VARCHAR(50),
    "fullName" VARCHAR(255),
    password VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    token VARCHAR(255),
    status VARCHAR(32) NOT NULL,
    "createdAt" DATETIME NOT NULL,
    "updatedAt" DATETIME NOT NULL
)
"""


@pytest.fixture
def stale_engine():
    """SQLite database holding only the users table of the old deployment."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text(STALE_USERS_DDL))
    yield engine
    engine.dispose()


def _column_names(engine, table: str = "users") -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table)}


def test_init_db_adds_the_missing_nullable_columns(stale_engine):
    init_db(stale_engine)

    assert _column_names(stale_engine) >= {
        "ruv",
        "expireAt",
        "id",
        "username",
        "status",
    }


def test_init_db_makes_the_stale_table_queryable_through_the_orm(stale_engine):
    from datetime import datetime, timezone

    init_db(stale_engine)
    session = sessionmaker(bind=stale_engine)()
    now = datetime.now(timezone.utc)
    stored = UserModel(
        id="00000000-0000-0000-0000-000000000001",
        username="ana",
        email="ana@example.com",
        password="hash",
        salt="salt",
        status="VERIFICADO",
        ruv="ruv-stored-by-the-model",
        expireAt=now,
        createdAt=now,
        updatedAt=now,
    )
    session.add(stored)
    session.commit()

    found = session.query(UserModel).filter_by(username="ana").one()

    assert found.ruv == "ruv-stored-by-the-model"
    assert found.status == "VERIFICADO"
    session.close()


def test_init_db_is_idempotent_on_a_stale_table(stale_engine):
    init_db(stale_engine)
    columns_after_first = _column_names(stale_engine)

    init_db(stale_engine)

    assert _column_names(stale_engine) == columns_after_first


def test_init_db_builds_a_fresh_database_with_the_full_schema():
    engine = create_engine("sqlite:///:memory:")
    try:
        init_db(engine)

        assert _column_names(engine) >= {
            "id",
            "username",
            "email",
            "status",
            "ruv",
            "expireAt",
        }
    finally:
        engine.dispose()


def test_init_db_refuses_to_guess_a_missing_required_column():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            # The stale deployment table without its required status column.
            connection.execute(
                text(
                    "CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, "
                    "username VARCHAR(100) NOT NULL, email VARCHAR(255) "
                    "NOT NULL, password VARCHAR(255) NOT NULL, salt "
                    "VARCHAR(255) NOT NULL, token VARCHAR(255))"
                )
            )

        with pytest.raises(RuntimeError, match="status"):
            init_db(engine)
    finally:
        engine.dispose()


def test_init_db_does_not_touch_tables_that_are_already_complete(stale_engine):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    with stale_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, username, email, password, salt, "
                "status, createdAt, updatedAt) VALUES "
                "('00000000-0000-0000-0000-000000000002', 'old', "
                "'old@example.com', 'hash', 'salt', 'VERIFICADO', "
                f"'{now.isoformat()}', '{now.isoformat()}')"
            )
        )

    init_db(stale_engine)

    with stale_engine.connect() as connection:
        row = connection.execute(
            text("SELECT username, status FROM users")
        ).one()

    assert row == ("old", "VERIFICADO")
