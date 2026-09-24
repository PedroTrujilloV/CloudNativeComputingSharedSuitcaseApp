"""Composition root of the card verification worker."""

from adapters.database import credit_card_status_adapter
from adapters.messaging import sns_card_result_publisher_adapter
from adapters.truenative import http_card_poller_adapter
from domain.use_cases.verify_card_status_use_case import VerifyCardStatusUseCase


def build_verify_card_status_use_case() -> VerifyCardStatusUseCase:
    """Wire the production adapters to the bounded polling use case."""
    return VerifyCardStatusUseCase(
        poller=http_card_poller_adapter.HttpCardPollerAdapter(),
        repository=credit_card_status_adapter.DynamoDbCardStatusAdapter(),
        publisher=sns_card_result_publisher_adapter.SnsCardResultPublisherAdapter(),
    )
