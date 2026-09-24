# Lambda container image for the card verification worker (matches
# config.yaml: card-worker). The image is consumed by the 6_lambda
# Terraform stack as the image_uri of the Lambda function; it is not
# deployed to Kubernetes.
# Build: docker build -t card-worker:v0.0.0 .

# The SAM base image ships the Lambda runtime interface client and the
# Python 3.11 interpreter under /var/lang. The application code lives in
# /var/task and the handler is declared with the CMD (module.function),
# which is how the Lambda runtime resolves the entry point of an image
# based function.
FROM public.ecr.aws/sam/python3.11-base

ENV POETRY_VERSION=2.1.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

WORKDIR /var/task

RUN pip install "poetry==${POETRY_VERSION}"

COPY poetry.lock pyproject.toml ./
COPY src/ ./

# Stub README: pyproject declares readme=README.md; real README is dockerignored.
RUN touch README.md \
    && poetry install --only main --no-root

# Lambda handler: handler module, handler function (see src/handler.py).
CMD ["handler.handler"]
