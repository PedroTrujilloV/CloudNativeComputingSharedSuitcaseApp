from adapters.database.credit_card_status_adapter import DynamoDbCardStatusAdapter
from adapters.messaging.sns_card_result_publisher_adapter import (
    SnsCardResultPublisherAdapter,
)
from adapters.truenative.http_card_poller_adapter import HttpCardPollerAdapter
from assembly import build_verify_card_status_use_case
from domain.use_cases.verify_card_status_use_case import VerifyCardStatusUseCase


def test_the_use_case_is_wired_with_the_production_adapters():
    use_case = build_verify_card_status_use_case()

    assert isinstance(use_case, VerifyCardStatusUseCase)
    assert isinstance(use_case.poller, HttpCardPollerAdapter)
    assert isinstance(use_case.repository, DynamoDbCardStatusAdapter)
    assert isinstance(use_case.publisher, SnsCardResultPublisherAdapter)


def test_the_defaults_of_the_wired_use_case_come_from_the_settings():
    from config import Settings

    use_case = build_verify_card_status_use_case()

    assert use_case.max_attempts == Settings.poll_max_attempts
    assert use_case.interval_seconds == Settings.poll_interval_seconds
    assert use_case.max_receives == Settings.max_receive_count
