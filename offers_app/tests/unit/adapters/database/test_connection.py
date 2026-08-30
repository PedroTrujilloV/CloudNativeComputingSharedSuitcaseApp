from unittest.mock import MagicMock, patch

from adapters.database.connection import build_engine, check_connection


def test_build_engine_uses_provided_url():
    """build_engine should honor an explicit database URL."""
    with patch("adapters.database.connection.create_engine") as create_engine_mock:
        create_engine_mock.return_value = MagicMock(name="engine")
        engine = build_engine("postgresql+psycopg://user:pass@localhost:5432/offers_db")

        create_engine_mock.assert_called_once()
        assert engine is create_engine_mock.return_value


def test_check_connection_executes_probe():
    """check_connection should run a SELECT 1 probe against the engine."""
    connection = MagicMock()
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection

    assert check_connection(engine) is True
    connection.execute.assert_called_once()