"""FastAPI application for the user verification callback receiver."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

from config import Settings
from entrypoints.api.routers.callback_router import router as callback_router


def _configure_logging() -> None:
    """Emit callback events at the configured ``LOG_LEVEL``.

    Uvicorn's default logging config leaves the root logger at WARNING,
    which would hide the INFO-level receipt and status-change events that
    are needed to debug the verification flow during grading or demo.
    """
    app_logger = logging.getLogger("user_verification_callback")
    app_logger.setLevel(Settings.log_level)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        app_logger.addHandler(handler)
    app_logger.propagate = False


_configure_logging()

app = FastAPI(title=Settings.app_name)
app.include_router(callback_router)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request: Request, _exc: RequestValidationError
):
    """Map request validation failures to HTTP 400 per API contract."""
    return Response(status_code=400)
