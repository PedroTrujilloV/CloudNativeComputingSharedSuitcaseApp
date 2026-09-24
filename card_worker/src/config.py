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
        return getenv("APP_NAME", "card_worker")

    @classmethod
    @property
    def log_level(cls) -> str:
        """Logging level from LOG_LEVEL env var."""
        return getenv("LOG_LEVEL", "INFO")

    @classmethod
    @property
    def aws_region(cls) -> str:
        """AWS region of the DynamoDB table and the SQS queue."""
        return getenv("AWS_REGION", "us-east-1")

    @classmethod
    @property
    def dynamodb_table_name(cls) -> str:
        """Name of the DynamoDB table of the CreditCard entity.

        The table is owned by the credit_cards_app and provisioned by the
        3_dynamodb Terraform stack; this worker is the only other component
        allowed to write it, and it updates only the status and the
        updatedAt of the card referenced by each event.
        """
        return getenv("DYNAMODB_TABLE_NAME", "credit_cards")

    @classmethod
    @property
    def truenative_url(cls) -> str:
        """Base URL of the TrueNative platform.

        The worker reaches the TrueNative service through the single
        external host of the platform (the load balancer of the ingress
        controller, /native prefix), the same host the rest of the system
        uses, so the function does not need any network attachment inside
        the cluster.
        """
        return getenv("TRUENATIVE_URL", "http://truenative-service")

    @classmethod
    @property
    def truenative_secret_token(cls) -> str:
        """Secret token required by TrueNative on every request.

        The value is injected by the 6_lambda stack from the
        secrets-pipeline-native-map secret in AWS Secrets Manager. It is
        never hardcoded in source.
        """
        return getenv("TRUENATIVE_SECRET_TOKEN", "")

    @classmethod
    @property
    def card_result_topic_arn(cls) -> str:
        """ARN of the SNS topic that receives the card result notification.

        While it is empty, the result publish is skipped and logged, so the
        worker can run before the 4_sns and 6_lambda wiring is in place.
        """
        return getenv("CARD_RESULT_TOPIC_ARN", "")

    @classmethod
    @property
    def max_receive_count(cls) -> int:
        """Maximum number of receives before the queue redrives the event.

        It must mirror the maxReceiveCount of the dead letter policy of the
        5_sqs stack: on the last receive the worker publishes the
        POR_VERIFICAR fallback email before the invocation fails and the
        event moves to the dead letter queue.
        """
        raw = getenv("MAX_RECEIVE_COUNT", "5")
        try:
            value = int(raw)
        except ValueError:
            return 5
        return value if value > 0 else 5

    @classmethod
    @property
    def poll_max_attempts(cls) -> int:
        """Maximum number of TrueNative polling attempts per invocation.

        When the attempts are exhausted the use case raises, so the queue
        redelivers the event; after the maximum number of receives the
        event is moved to the dead letter queue and the card stays
        POR_VERIFICAR.
        """
        raw = getenv("POLL_MAX_ATTEMPTS", "5")
        try:
            value = int(raw)
        except ValueError:
            return 5
        return value if value > 0 else 5

    @classmethod
    @property
    def poll_interval_seconds(cls) -> float:
        """Seconds to wait between two polling attempts."""
        raw = getenv("POLL_INTERVAL_SECONDS", "2")
        try:
            value = float(raw)
        except ValueError:
            return 2.0
        return value if value > 0 else 2.0

    @classmethod
    @property
    def http_timeout_seconds(cls) -> float:
        """Timeout of each TrueNative polling request."""
        raw = getenv("HTTP_TIMEOUT_SECONDS", "3")
        try:
            value = float(raw)
        except ValueError:
            return 3.0
        return value if value > 0 else 3.0
