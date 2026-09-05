"""FastAPI application for the RF-004 orchestrator."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

from config import Settings
from entrypoints.api.routers.rf004_router import router as rf004_router


def _configure_logging() -> None:
    """Emit orchestrator events at the configured ``LOG_LEVEL``.

    Uvicorn's default logging config leaves the root logger at WARNING,
    which would hide the INFO-level gate events that are needed to debug
    partial failures during grading/demo. A dedicated handler on the app
    logger keeps those events visible regardless of the ASGI server's
    logging configuration.
    """
    app_logger = logging.getLogger("rf004_create_offer_app")
    app_logger.setLevel(Settings.log_level)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        app_logger.addHandler(handler)
    app_logger.propagate = False


_configure_logging()

app = FastAPI(title=Settings.app_name)
app.include_router(rf004_router)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request: Request, _exc: RequestValidationError
):
    """Map request validation failures to HTTP 400 per API contract."""
    return Response(status_code=400)
