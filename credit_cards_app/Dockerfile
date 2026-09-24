# Multi-stage image for credit_cards_app (matches config.yaml: credit-cards-app).
# Build: docker build -t credit-cards-app:v0.0.0 .
# Run:   docker run --rm -p 8000:8000 credit-cards-app:v0.0.0

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
    APP_NAME=credit_cards_app

COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin
COPY --from=base /app/src ./src

RUN groupadd -r noroot && useradd -r -g noroot noroot \
    && chown -R noroot:noroot /app

USER noroot

EXPOSE 8000

# Liveness probe: the ping utility endpoint is the stable health probe
# (no auth, no persistence access, a plain text pong answer).
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/credit-cards/ping')" || exit 1

CMD ["uvicorn", "entrypoints.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
