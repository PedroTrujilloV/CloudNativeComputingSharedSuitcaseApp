import os
from unittest.mock import patch

from config import Settings


def test_default_users_service_url():
    """The status update target defaults to the in-cluster Users service name."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("USERS_SERVICE_URL", None)
        url = Settings.users_service_url

    assert url == "http://users-app-service:8000"


def test_users_service_url_from_environment():
    """USERS_SERVICE_URL overrides the in-cluster default."""
    with patch.dict(
        os.environ,
        {"USERS_SERVICE_URL": "http://users-app-service:8080"},
        clear=False,
    ):
        assert Settings.users_service_url == "http://users-app-service:8080"


def test_default_secret_token_is_empty():
    """Until the deployment provides the secret, the token is empty."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SECRET_TOKEN", None)
        assert Settings.secret_token == ""


def test_secret_token_from_environment():
    """SECRET_TOKEN comes from the environment (never hardcoded)."""
    with patch.dict(os.environ, {"SECRET_TOKEN": "top-secret"}, clear=False):
        assert Settings.secret_token == "top-secret"


def test_default_http_timeout():
    """Downstream calls time out after five seconds by default."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("HTTP_TIMEOUT", None)
        assert Settings.http_timeout == 5.0


def test_http_timeout_from_environment():
    """HTTP_TIMEOUT overrides the default timeout."""
    with patch.dict(os.environ, {"HTTP_TIMEOUT": "12"}, clear=False):
        assert Settings.http_timeout == 12.0


def test_default_app_name():
    """Application name matches the component folder by default."""
    assert Settings.app_name == "user_verification_callback"


def test_log_level_from_environment():
    """LOG_LEVEL is read from the environment at configuration time."""
    with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}, clear=False):
        assert Settings.log_level == "WARNING"


def test_default_user_verification_topic_arn_is_empty():
    """Until the deploy pipeline provides the topic ARN, it is empty."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("USER_VERIFICATION_TOPIC_ARN", None)
        assert Settings.user_verification_topic_arn == ""


def test_user_verification_topic_arn_from_environment():
    """USER_VERIFICATION_TOPIC_ARN comes from the environment (4_sns output)."""
    arn = "arn:aws:sns:us-east-1:123456789012:grupo33-user-verification-notifications"
    with patch.dict(os.environ, {"USER_VERIFICATION_TOPIC_ARN": arn}, clear=False):
        assert Settings.user_verification_topic_arn == arn


def test_default_aws_region():
    """The SNS client defaults to the region of the course AWS account."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AWS_REGION", None)
        assert Settings.aws_region == "us-east-1"


def test_aws_region_from_environment():
    """AWS_REGION overrides the default region."""
    with patch.dict(os.environ, {"AWS_REGION": "eu-west-1"}, clear=False):
        assert Settings.aws_region == "eu-west-1"


def test_default_sns_endpoint_url_is_empty():
    """Production runs use the real AWS endpoint (no override)."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SNS_ENDPOINT_URL", None)
        assert Settings.sns_endpoint_url == ""


def test_sns_endpoint_url_from_environment():
    """SNS_ENDPOINT_URL overrides the endpoint (local simulation)."""
    with patch.dict(
        os.environ, {"SNS_ENDPOINT_URL": "http://localhost:5000"}, clear=False
    ):
        assert Settings.sns_endpoint_url == "http://localhost:5000"
