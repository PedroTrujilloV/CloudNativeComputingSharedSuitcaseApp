from contextlib import asynccontextmanager

from adapters.database.connection import init_db
from config import Settings
from entrypoints.api.routers.offer_router import router as offer_router
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create tables on startup against the configured database."""
    init_db()
    yield


app = FastAPI(title=Settings.app_name, lifespan=lifespan)
app.include_router(offer_router)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request: Request, _exc: RequestValidationError
):
    """Map missing or malformed request fields to HTTP 400 per API contract.

    Values that pass schema validation but fail domain rules (e.g. negative
    offer, invalid size) are handled inside the use-case and return 412.
    """
    return Response(status_code=400)