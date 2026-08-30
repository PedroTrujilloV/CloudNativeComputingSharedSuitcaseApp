"""
Posts Service Application Entry Point.
FastAPI application for managing Publications (Publicaciones).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

from config import Settings
from entrypoints.api.routers.posts_router import router as posts_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize database on startup."""
    from adapters.database.connection import init_db
    init_db()
    yield


app = FastAPI(title=Settings.app_name, lifespan=lifespan)
app.include_router(posts_router)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request: Request, _exc: RequestValidationError
):
    """Map request validation failures to HTTP 400 per API contract."""
    return Response(status_code=400)
