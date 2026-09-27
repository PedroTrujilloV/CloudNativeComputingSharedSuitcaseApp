import os


class Settings:
    """Application settings loaded from environment variables."""

    @classmethod
    @property
    def app_name(cls) -> str:
        """Application name (FastAPI title)."""
        return os.getenv("APP_NAME", "user_verification_callback")

    @classmethod
    @property
    def log_level(cls) -> str:
        """Logging level for the application logger."""
        return os.getenv("LOG_LEVEL", "DEBUG")

    @classmethod
    @property
    def users_service_url(self) -> str:
        """Base URL of the Users service (status update target).

        In Minikube/EKS the service is reachable through the cluster DNS
        name ``users-app-service``; locally it can be pointed at
        localhost so the callback can be tested next to a running
        users_app.
        """
        return os.getenv("USERS_SERVICE_URL", "http://users-app-service:8000")

    @classmethod
    @property
    def secret_token(self) -> str:
        """Secret token shared with the TrueNative deployment.

        It is the first part of the callback signature
        ``sha256(f"{SECRET_TOKEN}:{RUV}:{SCORE}")`` and must match the
        ``SECRET_TOKEN`` environment variable of the TrueNative deployment
        (the ``truenative-secret`` Kubernetes Secret). It is provided through
        the environment and never hardcoded in source.
        """
        return os.getenv("SECRET_TOKEN", "")

    @classmethod
    @property
    def http_timeout(self) -> float:
        """Timeout in seconds for the downstream status update call."""
        return float(os.getenv("HTTP_TIMEOUT", "5"))

    @classmethod
    @property
    def user_verification_topic_arn(cls) -> str:
        """ARN of the RF-007 SNS email topic.

        The callback manifest
        (``k8s_entrega2/28-user-verification-callback.yml``) reconstructs
        the full ARN at apply time from the safe
        ``user_verification_topic_name`` output of the ``4_sns`` stack
        plus ``$AWS_REGION`` and ``$ACCOUNT_ID`` (the full ARN embeds the
        AWS account id, so it cannot be a terraform output of the
        pipeline), and the deploy pipeline envsubst fills the
        ``${USER_VERIFICATION_TOPIC_ARN}`` placeholder. When the value
        is empty (local runs without the AWS stack) the email
        notification is skipped with a logged notice.
        """
        return os.getenv("USER_VERIFICATION_TOPIC_ARN", "")

    @classmethod
    @property
    def aws_region(cls) -> str:
        """AWS region for the SNS client."""
        return os.getenv("AWS_REGION", "us-east-1")

    @classmethod
    @property
    def sns_endpoint_url(cls) -> str:
        """Optional endpoint override for the SNS client.

        It is empty in production; a local run can point it at an SNS
        simulation to exercise the publish path without AWS credentials.
        """
        return os.getenv("SNS_ENDPOINT_URL", "")
