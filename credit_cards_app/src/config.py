"""
Application configuration module.
Loads settings from environment variables.
"""

from os import getenv


class Settings:
    """Application settings loaded from environment variables."""

    @classmethod
    @property
    def app_name(cls) -> str:
        """Application name from APP_NAME env var."""
        return getenv("APP_NAME", "credit_cards_app")

    @classmethod
    @property
    def log_level(cls) -> str:
        """Logging level from LOG_LEVEL env var."""
        return getenv("LOG_LEVEL", "INFO")

    @classmethod
    @property
    def aws_region(cls) -> str:
        """AWS region that hosts the DynamoDB table."""
        return getenv("AWS_REGION", "us-east-1")

    @classmethod
    @property
    def dynamodb_table_name(cls) -> str:
        """Name of the DynamoDB table owned by this application.

        The table is provisioned by the 3_dynamodb Terraform stack and is
        exclusive to this application: no other component reads or writes it
        except the card worker, through the same DynamoDB API.
        """
        return getenv("DYNAMODB_TABLE_NAME", "credit_cards")

    @classmethod
    @property
    def users_app_url(cls) -> str:
        """Base URL of the users application, used to validate bearer tokens.

        The credit cards application never touches the users database
        directly: it calls the public ``GET /users/me`` endpoint of the users
        application over HTTP/REST.
        """
        return getenv("USERS_APP_URL", "http://users-app-service:8000")

    @classmethod
    @property
    def truenative_url(cls) -> str:
        """Base URL of the TrueNative platform (card tokenization)."""
        return getenv("TRUENATIVE_URL", "http://truenative-service")

    @classmethod
    @property
    def truenative_secret_token(cls) -> str:
        """Secret token required by TrueNative on every request.

        The value comes from the ``truenative-secret`` Kubernetes secret in
        the cluster and from a local environment variable when running
        outside the cluster. It is never hardcoded in source.
        """
        return getenv("TRUENATIVE_SECRET_TOKEN", "")

    @classmethod
    @property
    def card_verification_queue_url(cls) -> str:
        """URL of the SQS queue that receives the card verification events.

        The queue is provisioned by the serverless stack of the card worker
        (a later task of the epic). While it is empty, the application runs
        without the asynchronous hand off and only logs the skipped publish,
        so the synchronous creation flow stays fully functional.
        """
        return getenv("CARD_VERIFICATION_QUEUE_URL", "")

    @classmethod
    @property
    def http_timeout_seconds(cls) -> float:
        """Timeout for the synchronous HTTP calls to users_app and TrueNative.

        The whole creation request must answer in under five seconds, so the
        two upstream calls share a bounded budget instead of hanging.
        """
        raw = getenv("HTTP_TIMEOUT_SECONDS", "3")
        try:
            timeout = float(raw)
        except ValueError:
            return 3.0
        return timeout if timeout > 0 else 3.0
