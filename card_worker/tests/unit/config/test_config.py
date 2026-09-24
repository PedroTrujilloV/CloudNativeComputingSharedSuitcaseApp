import os

import pytest

from config import Settings


@pytest.fixture
def restore_env():
    """Snapshot the environment and restore it after each test."""
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)


def test_the_app_name_comes_from_the_environment(restore_env):
    os.environ["APP_NAME"] = "card_worker_test"
    assert Settings.app_name == "card_worker_test"


def test_the_app_name_has_a_default(restore_env):
    os.environ.pop("APP_NAME", None)
    assert Settings.app_name == "card_worker"


def test_the_aws_region_comes_from_the_environment(restore_env):
    os.environ["AWS_REGION"] = "eu-west-1"
    assert Settings.aws_region == "eu-west-1"


def test_the_aws_region_has_a_default(restore_env):
    os.environ.pop("AWS_REGION", None)
    assert Settings.aws_region == "us-east-1"


def test_the_dynamodb_table_name_comes_from_the_environment(restore_env):
    os.environ["DYNAMODB_TABLE_NAME"] = "my-table"
    assert Settings.dynamodb_table_name == "my-table"


def test_the_dynamodb_table_name_has_a_default(restore_env):
    os.environ.pop("DYNAMODB_TABLE_NAME", None)
    assert Settings.dynamodb_table_name == "credit_cards"


def test_the_truenative_url_comes_from_the_environment(restore_env):
    os.environ["TRUENATIVE_URL"] = "https://host.example"
    assert Settings.truenative_url == "https://host.example"


def test_the_truenative_secret_token_comes_from_the_environment(restore_env):
    os.environ["TRUENATIVE_SECRET_TOKEN"] = "tok"
    assert Settings.truenative_secret_token == "tok"


def test_the_truenative_secret_token_defaults_to_empty(restore_env):
    os.environ.pop("TRUENATIVE_SECRET_TOKEN", None)
    assert Settings.truenative_secret_token == ""


def test_the_card_result_topic_arn_defaults_to_empty(restore_env):
    os.environ.pop("CARD_RESULT_TOPIC_ARN", None)
    assert Settings.card_result_topic_arn == ""


def test_the_card_result_topic_arn_comes_from_the_environment(restore_env):
    os.environ["CARD_RESULT_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123:card-result"
    assert Settings.card_result_topic_arn == "arn:aws:sns:us-east-1:123:card-result"


def test_the_max_receive_count_comes_from_the_environment(restore_env):
    os.environ["MAX_RECEIVE_COUNT"] = "7"
    assert Settings.max_receive_count == 7


def test_the_max_receive_count_has_a_default(restore_env):
    os.environ.pop("MAX_RECEIVE_COUNT", None)
    assert Settings.max_receive_count == 5


def test_an_invalid_max_receive_count_falls_back_to_the_default(restore_env):
    os.environ["MAX_RECEIVE_COUNT"] = "not-a-number"
    assert Settings.max_receive_count == 5


def test_a_non_positive_max_receive_count_falls_back_to_the_default(restore_env):
    os.environ["MAX_RECEIVE_COUNT"] = "0"
    assert Settings.max_receive_count == 5


def test_the_poll_max_attempts_comes_from_the_environment(restore_env):
    os.environ["POLL_MAX_ATTEMPTS"] = "7"
    assert Settings.poll_max_attempts == 7


def test_an_invalid_poll_max_attempts_falls_back_to_the_default(restore_env):
    os.environ["POLL_MAX_ATTEMPTS"] = "not-a-number"
    assert Settings.poll_max_attempts == 5


def test_a_non_positive_poll_max_attempts_falls_back_to_the_default(restore_env):
    os.environ["POLL_MAX_ATTEMPTS"] = "0"
    assert Settings.poll_max_attempts == 5


def test_the_poll_interval_comes_from_the_environment(restore_env):
    os.environ["POLL_INTERVAL_SECONDS"] = "1.5"
    assert Settings.poll_interval_seconds == 1.5


def test_an_invalid_poll_interval_falls_back_to_the_default(restore_env):
    os.environ["POLL_INTERVAL_SECONDS"] = "soon"
    assert Settings.poll_interval_seconds == 2.0


def test_the_http_timeout_comes_from_the_environment(restore_env):
    os.environ["HTTP_TIMEOUT_SECONDS"] = "10"
    assert Settings.http_timeout_seconds == 10.0


def test_an_invalid_http_timeout_falls_back_to_the_default(restore_env):
    os.environ["HTTP_TIMEOUT_SECONDS"] = "soon"
    assert Settings.http_timeout_seconds == 3.0
