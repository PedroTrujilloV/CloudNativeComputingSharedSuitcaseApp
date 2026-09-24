from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

from config import Settings
from entrypoints.api.routers.credit_card_router import router as credit_card_router
from errors import (
    AuthTokenMissingError,
    InvalidTokenError,
    UserVerificationUnavailableError,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Log the persistence wiring for the operators.

    Every business endpoint of the RF-006 API is live on this
    application: the creation flow, the listing, and the utility
    endpoints (count, ping, reset).
    """
    print(
        f"{Settings.app_name} started: DynamoDB table "
        f"'{Settings.dynamodb_table_name}' in region '{Settings.aws_region}'"
    )
    yield


app = FastAPI(title=Settings.app_name, lifespan=lifespan)
app.include_router(credit_card_router)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request: Request, _exc: RequestValidationError
):
    """Map missing or malformed request fields to HTTP 400 per API contract.

    Values that pass schema validation but fail domain rules (an expired
    card, a duplicate card) are handled inside the use case and return
    412 and 409 respectively.
    """
    return Response(status_code=400)


@app.exception_handler(AuthTokenMissingError)
async def auth_token_missing_exception_handler(
    _request: Request, _exc: AuthTokenMissingError
):
    """Map a request without any bearer token to HTTP 403 per API contract."""
    return Response(status_code=403)


@app.exception_handler(InvalidTokenError)
async def invalid_token_exception_handler(
    _request: Request, _exc: InvalidTokenError
):
    """Map an invalid or expired bearer token to HTTP 401 per API contract."""
    return Response(status_code=401)


@app.exception_handler(UserVerificationUnavailableError)
async def user_verification_unavailable_exception_handler(
    _request: Request, _exc: UserVerificationUnavailableError
):
    """Map a users application failure to HTTP 502 (bad gateway)."""
    return Response(status_code=502)
