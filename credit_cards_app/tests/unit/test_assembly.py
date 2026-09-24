from adapters.database.credit_card_repository_adapter import (
    DynamoDbCreditCardRepositoryAdapter,
)
from adapters.messaging.card_event_publisher_adapter import (
    SqsCardEventPublisherAdapter,
)
from adapters.truenative.true_native_adapter import HttpTrueNativeAdapter
from adapters.users.user_verification_adapter import UsersAppUserVerificationAdapter
from config import Settings
from domain.ports.card_event_publisher_port import CardEventPublisherPort
from domain.ports.credit_card_repository_port import CreditCardRepositoryPort
from domain.ports.true_native_port import TrueNativePort
from domain.ports.user_token_verification_port import UserTokenVerificationPort

from assembly import (
    build_card_event_publisher,
    build_credit_card_repository,
    build_true_native,
    build_user_verification,
)


def test_build_credit_card_repository_returns_the_dynamodb_adapter(
    dynamodb_resource,
):
    repository = build_credit_card_repository()

    assert isinstance(repository, CreditCardRepositoryPort)
    assert isinstance(repository, DynamoDbCreditCardRepositoryAdapter)


def test_repository_is_bound_to_the_configured_table(dynamodb_resource):
    repository = build_credit_card_repository()

    assert repository.table_name == Settings.dynamodb_table_name
    assert repository.table.table_name == Settings.dynamodb_table_name


def test_build_user_verification_returns_the_users_app_adapter():
    adapter = build_user_verification()

    assert isinstance(adapter, UserTokenVerificationPort)
    assert isinstance(adapter, UsersAppUserVerificationAdapter)
    assert adapter.base_url == Settings.users_app_url.rstrip("/")


def test_build_true_native_returns_the_http_adapter():
    adapter = build_true_native()

    assert isinstance(adapter, TrueNativePort)
    assert isinstance(adapter, HttpTrueNativeAdapter)
    assert adapter.base_url == Settings.truenative_url.rstrip("/")
    assert adapter.secret_token == Settings.truenative_secret_token


def test_build_card_event_publisher_returns_the_sqs_adapter():
    publisher = build_card_event_publisher()

    assert isinstance(publisher, CardEventPublisherPort)
    assert isinstance(publisher, SqsCardEventPublisherAdapter)
    assert publisher.queue_url == Settings.card_verification_queue_url
