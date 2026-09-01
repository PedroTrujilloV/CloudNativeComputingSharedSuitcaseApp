from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

from adapters.database.connection import init_db
from config import Settings
from entrypoints.api.routers.score_router import router as score_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create tables on startup, retrying until PostgreSQL is ready."""
    max_retries = 30
    for attempt in range(1, max_retries + 1):
        try:
            init_db()
            break
        except Exception:
            if attempt == max_retries:
                raise
            time.sleep(2)
    yield


app = FastAPI(title=Settings.app_name, lifespan=lifespan)
app.include_router(score_router)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request: Request, _exc: RequestValidationError
):
    """Map request validation failures to HTTP 400 per API contract."""
    return Response(status_code=400)
