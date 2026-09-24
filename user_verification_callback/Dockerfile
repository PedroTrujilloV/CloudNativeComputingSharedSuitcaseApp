# Multi-stage image for user_verification_callback (matches config.yaml:
# user-verification-callback:v0.0.0).
# Build: docker build -t user-verification-callback:v0.0.0 .
# Run:   docker run --rm -p 8000:8000 user-verification-callback:v0.0.0
#
# The callback receiver is stateless: it owns no database. It receives the
# public TrueNative callback, verifies the SHA256 signature, and updates the
# user status through the Users service API (USERS_SERVICE_URL). All the work
# happens synchronously inside the request; there is no background processing.

# ---------------------------------------------------------------------------
# Stage base: install runtime dependencies with Poetry
# ---------------------------------------------------------------------------
FROM python:3.11.11-slim AS base

WORKDIR /app

ENV POETRY_VERSION=2.1.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN pip install "poetry==${POETRY_VERSION}"

COPY poetry.lock pyproject.toml ./
COPY src/ src/

# Stub README: pyproject declares readme=README.md; real README is dockerignored.
RUN touch README.md \
    && poetry install --only main --no-ansi --no-root

# ---------------------------------------------------------------------------
# Stage runner: lean runtime image without Poetry
# ---------------------------------------------------------------------------
FROM python:3.11.11-slim AS runner

WORKDIR /app

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    APP_NAME=user_verification_callback

COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin
COPY --from=base /app/src ./src

RUN groupadd -r noroot && useradd -r -g noroot noroot \
    && chown -R noroot:noroot /app

USER noroot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/users/verify/ping')" || exit 1

CMD ["uvicorn", "entrypoints.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
