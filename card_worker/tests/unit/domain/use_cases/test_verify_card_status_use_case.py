import re
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from config import Settings
from domain.models.card_status import CardStatus
from domain.models.card_verification_event import CardVerificationEvent
from domain.ports.true_native_poller_port import CardPollingResult
from domain.use_cases.verify_card_status_use_case import VerifyCardStatusUseCase
from errors import CardVerificationPendingError


def card_id_of(label: str) -> str:
    """Deterministic UUID per label (the event model requires a UUID)."""
    return str(uuid5(NAMESPACE_URL, f"card-{label}"))


class ScriptedPoller:
    """Poller that returns a scripted sequence of attempts."""

    def __init__(self, results: list[CardPollingResult]):
        self.results = list(results)
        self.calls = []

    def check_status(self, ruv: str) -> CardPollingResult:
        self.calls.append(ruv)
        return self.results.pop(0)


class RecordingRepository:
    def __init__(self):
        self.updates = []

    def update_status(self, card_id: str, status: CardStatus) -> None:
        self.updates.append((card_id, status))


class RecordingPublisher:
    """Publisher stand in: records the notification calls."""

    def __init__(self, fail: bool = False):
        self.calls = []
        self.fail = fail

    def publish_card_result(
        self,
        card_id: str,
        status: str,
        ruv: str,
        last_four_digits: str,
        issuer: str,
        updated_at: str,
        owner_email: str,
    ) -> None:
        if self.fail:
            raise RuntimeError("sns unreachable")
        self.calls.append(
            {
                "card_id": card_id,
                "status": status,
                "ruv": ruv,
                "last_four_digits": last_four_digits,
                "issuer": issuer,
                "updated_at": updated_at,
                "owner_email": owner_email,
            }
        )


def make_event(label: str = "1", ruv: str = "ruv-1") -> CardVerificationEvent:
    # Dates are computed at test time (no fixed dates).
    return CardVerificationEvent(
        eventType="CARD_VERIFICATION_REQUESTED",
        cardId=card_id_of(label),
        ruv=ruv,
        userId="user-1",
        lastFourDigits="4242",
        issuer="VISA",
        status="POR_VERIFICAR",
        createdAt=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        ownerEmail="owner@example.com",
    )


def make_use_case(
    poller,
    repository,
    publisher=None,
    max_receives=None,
):
    recorded = []

    def sleep(seconds: float) -> None:
        recorded.append(seconds)

    use_case = VerifyCardStatusUseCase(
        poller=poller,
        repository=repository,
        publisher=publisher if publisher is not None else RecordingPublisher(),
        max_receives=max_receives,
        sleep=sleep,
    )
    return use_case, recorded


def pending() -> CardPollingResult:
    return CardPollingResult(terminal=False)


def terminal(status: str) -> CardPollingResult:
    return CardPollingResult(terminal=True, status=status)


def test_a_terminal_first_answer_updates_the_card_and_publishes_the_email():
    poller = ScriptedPoller([terminal("APROBADA")])
    repository = RecordingRepository()
    publisher = RecordingPublisher()
    use_case, sleeps = make_use_case(poller, repository, publisher)

    result = use_case.execute(make_event())

    assert result == CardStatus.APROBADA
    assert repository.updates == [(card_id_of("1"), CardStatus.APROBADA)]
    assert poller.calls == ["ruv-1"]
    assert sleeps == []
    assert len(publisher.calls) == 1
    notification = publisher.calls[0]
    assert notification["card_id"] == card_id_of("1")
    assert notification["status"] == "APROBADA"
    assert notification["ruv"] == "ruv-1"
    assert notification["last_four_digits"] == "4242"
    assert notification["issuer"] == "VISA"
    assert notification["owner_email"] == "owner@example.com"
    # The notification carries the stored card data and the RUV, and the
    # updated date follows the entity contract (ISO, second precision).
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", notification["updated_at"]
    )


def test_a_pending_answer_is_retried_after_the_interval():
    poller = ScriptedPoller([pending(), pending(), terminal("RECHAZADA")])
    repository = RecordingRepository()
    publisher = RecordingPublisher()
    use_case, sleeps = make_use_case(poller, repository, publisher)

    result = use_case.execute(make_event("2"))

    assert result == CardStatus.RECHAZADA
    assert repository.updates == [(card_id_of("2"), CardStatus.RECHAZADA)]
    assert len(poller.calls) == 3
    # The wait happens between attempts, never before the first poll.
    assert sleeps == [use_case.interval_seconds, use_case.interval_seconds]
    # The email is published once, for the terminal state.
    assert [call["status"] for call in publisher.calls] == ["RECHAZADA"]


def test_exhausted_attempts_raise_and_skip_the_repository_and_the_email():
    poller = ScriptedPoller([pending(), pending(), pending()])
    repository = RecordingRepository()
    publisher = RecordingPublisher()
    use_case, _ = make_use_case(poller, repository, publisher)

    with pytest.raises(CardVerificationPendingError):
        use_case.execute(make_event("3"))

    assert len(poller.calls) == use_case.max_attempts
    assert repository.updates == []
    # The event is not on its last receive, so no notification is sent yet.
    assert publisher.calls == []


def test_the_fallback_email_is_published_on_the_last_receive():
    poller = ScriptedPoller([pending(), pending(), pending()])
    repository = RecordingRepository()
    publisher = RecordingPublisher()
    use_case, _ = make_use_case(poller, repository, publisher, max_receives=5)

    with pytest.raises(CardVerificationPendingError):
        use_case.execute(make_event(), receive_count=5)

    assert repository.updates == []
    assert len(publisher.calls) == 1
    notification = publisher.calls[0]
    # The owner is never left without the mandatory notification: the
    # fallback carries the POR_VERIFICAR status and the RUV.
    assert notification["status"] == "POR_VERIFICAR"
    assert notification["ruv"] == "ruv-1"
    assert notification["card_id"] == card_id_of("1")


def test_no_fallback_email_before_the_last_receive():
    poller = ScriptedPoller([pending(), pending(), pending()])
    repository = RecordingRepository()
    publisher = RecordingPublisher()
    use_case, _ = make_use_case(poller, repository, publisher, max_receives=5)

    with pytest.raises(CardVerificationPendingError):
        use_case.execute(make_event(), receive_count=4)

    assert publisher.calls == []


def test_a_fallback_publish_failure_is_logged_not_raised():
    poller = ScriptedPoller([pending(), pending(), pending()])
    repository = RecordingRepository()
    publisher = RecordingPublisher(fail=True)
    use_case, _ = make_use_case(poller, repository, publisher, max_receives=1)

    # The invocation fails with the pending error either way; the publish
    # failure must not mask it.
    with pytest.raises(CardVerificationPendingError):
        use_case.execute(make_event(), receive_count=1)


def test_a_terminal_publish_failure_propagates_for_the_redelivery():
    poller = ScriptedPoller([terminal("APROBADA")])
    repository = RecordingRepository()
    publisher = RecordingPublisher(fail=True)
    use_case, _ = make_use_case(poller, repository, publisher)

    # The status is already persisted; the publish failure must propagate
    # so the queue redelivers the event and the notification is retried.
    with pytest.raises(RuntimeError):
        use_case.execute(make_event())

    assert repository.updates == [(card_id_of("1"), CardStatus.APROBADA)]


def test_the_defaults_coming_from_the_settings_are_used():
    poller = ScriptedPoller([terminal("APROBADA")])
    repository = RecordingRepository()
    publisher = RecordingPublisher()
    use_case = VerifyCardStatusUseCase(
        poller=poller, repository=repository, publisher=publisher
    )

    use_case.execute(make_event("4"))

    assert use_case.max_attempts == Settings.poll_max_attempts
    assert use_case.interval_seconds == Settings.poll_interval_seconds
    assert use_case.max_receives == Settings.max_receive_count
    assert repository.updates == [(card_id_of("4"), CardStatus.APROBADA)]
    assert len(publisher.calls) == 1


def test_the_use_case_stops_as_soon_as_the_terminal_state_is_reached():
    poller = ScriptedPoller([pending(), terminal("RECHAZADA"), terminal("APROBADA")])
    repository = RecordingRepository()
    publisher = RecordingPublisher()
    use_case, _ = make_use_case(poller, repository, publisher)

    use_case.execute(make_event("5"))

    assert len(poller.calls) == 2
    assert repository.updates == [(card_id_of("5"), CardStatus.RECHAZADA)]
    assert [call["status"] for call in publisher.calls] == ["RECHAZADA"]


def test_an_event_without_an_owner_email_is_still_notified():
    # Events published before the ownerEmail wiring carry no address; the
    # notification is still produced (the topic subscription decides the
    # delivery address).
    poller = ScriptedPoller([terminal("APROBADA")])
    repository = RecordingRepository()
    publisher = RecordingPublisher()
    use_case, _ = make_use_case(poller, repository, publisher)
    event = make_event()
    event = event.model_copy(update={"ownerEmail": ""})

    use_case.execute(event)

    assert publisher.calls[0]["owner_email"] == ""
