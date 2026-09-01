import asyncio
from unittest.mock import patch

from entrypoints.api.main import app, lifespan


def test_lifespan_retries_until_database_is_ready():
    calls = {"n": 0}

    def flaky_init_db():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("database is not ready")

    async def _run():
        with patch("entrypoints.api.main.init_db", side_effect=flaky_init_db):
            with patch("entrypoints.api.main.time.sleep", return_value=None):
                async with lifespan(app):
                    pass

    asyncio.run(_run())
    assert calls["n"] == 3
