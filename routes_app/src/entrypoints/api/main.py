from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from adapters.database.connection import init_db
from config import Settings
from entrypoints.api.routers.routes_router import router as routes_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create tables on startup, retrying until the database is ready."""
    max_retries = 30
    for i in range(1, max_retries + 1):
        try:
            init_db()
            break
        except Exception:
            if i == max_retries:
                raise
            time.sleep(2)
    yield


app = FastAPI(title=Settings.app_name, lifespan=lifespan)
app.include_router(routes_router)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> Response:
    """Map request validation failures to HTTP 400 per API contract."""
    return Response(status_code=400, media_type="application/json")