def test_app_name_defaults_to_credit_cards_app(monkeypatch):
    from config import Settings

    monkeypatch.delenv("APP_NAME", raising=False)
    assert Settings.app_name == "credit_cards_app"


def test_app_name_reads_env(monkeypatch):
    from config import Settings

    monkeypatch.setenv("APP_NAME", "custom_app")
    assert Settings.app_name == "custom_app"


def test_log_level_defaults_to_info(monkeypatch):
    from config import Settings

    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert Settings.log_level == "INFO"


def test_aws_region_defaults_to_us_east_1(monkeypatch):
    from config import Settings

    monkeypatch.delenv("AWS_REGION", raising=False)
    assert Settings.aws_region == "us-east-1"


def test_aws_region_reads_env(monkeypatch):
    from config import Settings

    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    assert Settings.aws_region == "eu-west-1"


def test_dynamodb_table_name_defaults_to_credit_cards(monkeypatch):
    from config import Settings

    monkeypatch.delenv("DYNAMODB_TABLE_NAME", raising=False)
    assert Settings.dynamodb_table_name == "credit_cards"


def test_dynamodb_table_name_reads_env(monkeypatch):
    from config import Settings

    monkeypatch.setenv("DYNAMODB_TABLE_NAME", "custom_table")
    assert Settings.dynamodb_table_name == "custom_table"


def test_users_app_url_defaults_to_the_cluster_service(monkeypatch):
    from config import Settings

    monkeypatch.delenv("USERS_APP_URL", raising=False)
    assert Settings.users_app_url == "http://users-app-service:8000"


def test_users_app_url_reads_env(monkeypatch):
    from config import Settings

    monkeypatch.setenv("USERS_APP_URL", "http://localhost:8000")
    assert Settings.users_app_url == "http://localhost:8000"


def test_truenative_url_defaults_to_the_cluster_service(monkeypatch):
    from config import Settings

    monkeypatch.delenv("TRUENATIVE_URL", raising=False)
    assert Settings.truenative_url == "http://truenative-service"


def test_truenative_url_reads_env(monkeypatch):
    from config import Settings

    monkeypatch.setenv("TRUENATIVE_URL", "http://localhost:3000")
    assert Settings.truenative_url == "http://localhost:3000"


def test_truenative_secret_token_defaults_to_empty(monkeypatch):
    from config import Settings

    monkeypatch.delenv("TRUENATIVE_SECRET_TOKEN", raising=False)
    assert Settings.truenative_secret_token == ""


def test_truenative_secret_token_reads_env(monkeypatch):
    from config import Settings

    monkeypatch.setenv("TRUENATIVE_SECRET_TOKEN", "a-secret")
    assert Settings.truenative_secret_token == "a-secret"


def test_card_verification_queue_url_defaults_to_empty(monkeypatch):
    from config import Settings

    monkeypatch.delenv("CARD_VERIFICATION_QUEUE_URL", raising=False)
    assert Settings.card_verification_queue_url == ""


def test_card_verification_queue_url_reads_env(monkeypatch):
    from config import Settings

    monkeypatch.setenv(
        "CARD_VERIFICATION_QUEUE_URL", "http://sqs.test/queue"
    )
    assert Settings.card_verification_queue_url == "http://sqs.test/queue"


def test_http_timeout_seconds_defaults_to_three(monkeypatch):
    from config import Settings

    monkeypatch.delenv("HTTP_TIMEOUT_SECONDS", raising=False)
    assert Settings.http_timeout_seconds == 3.0


def test_http_timeout_seconds_reads_env(monkeypatch):
    from config import Settings

    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "2.5")
    assert Settings.http_timeout_seconds == 2.5


def test_http_timeout_seconds_falls_back_on_bad_values(monkeypatch):
    from config import Settings

    for bad_value in ("not-a-number", "0", "-1"):
        monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", bad_value)
        assert Settings.http_timeout_seconds == 3.0
