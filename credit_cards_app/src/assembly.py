"""Dependency injection wiring for the Credit Cards application."""

from adapters.database.connection import get_resource
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


def build_credit_card_repository() -> CreditCardRepositoryPort:
    """Build the DynamoDB credit card repository for the configured table."""
    return DynamoDbCreditCardRepositoryAdapter(
        table=get_resource().Table(Settings.dynamodb_table_name),
        table_name=Settings.dynamodb_table_name,
    )


def build_user_verification() -> UserTokenVerificationPort:
    """Build the users application token verification adapter."""
    return UsersAppUserVerificationAdapter()


def build_true_native() -> TrueNativePort:
    """Build the TrueNative tokenization adapter."""
    return HttpTrueNativeAdapter()


def build_card_event_publisher() -> CardEventPublisherPort:
    """Build the SQS card verification event publisher."""
    return SqsCardEventPublisherAdapter()


__all__ = [
    "build_card_event_publisher",
    "build_credit_card_repository",
    "build_true_native",
    "build_user_verification",
]
