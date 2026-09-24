from datetime import datetime, timezone

from domain.models.credit_card import CardIssuer, CardStatus, CreditCard
from domain.ports.card_event_publisher_port import CardEventPublisherPort
from domain.ports.credit_card_repository_port import CreditCardRepositoryPort
from domain.ports.true_native_port import (
    TrueNativePort,
    TrueNativeRegistration,
)
from domain.use_cases.create_credit_card_use_case import CreateCreditCardUseCase
from errors import (
    CardExpiredError,
    DuplicateCreditCardError,
    TrueNativeRegistrationError,
)

VALID_CARD_NUMBER = "4242424242424242"
VALID_CVV = "123"
VALID_HOLDER = "Jane Doe"
# The expiration is always far in the future relative to the run date, so
# the test cannot expire with time (no hardcoded date anywhere).
FAR_FUTURE_EXPIRATION = "99/12"


class InMemoryCreditCardRepository(CreditCardRepositoryPort):
    """Repository fake that keeps the cards in a plain list."""

    def __init__(self):
        self.cards: list[CreditCard] = []

    def create(self, card: CreditCard) -> CreditCard:
        self.cards.append(card)
        return card

    def get_by_id(self, card_id: str):
        for card in self.cards:
            if card.id == card_id:
                return card
        return None

    def search(self, user_id: str | None = None) -> list[CreditCard]:
        if user_id is None:
            return list(self.cards)
        return [card for card in self.cards if card.userId == user_id]

    def update_status(self, card_id: str, status: CardStatus):
        card = self.get_by_id(card_id)
        if card is None:
            return None
        updated = card.model_copy(update={"status": status})
        self.cards[self.cards.index(card)] = updated
        return updated

    def count(self) -> int:
        return len(self.cards)

    def delete_all(self) -> int:
        deleted = len(self.cards)
        self.cards = []
        return deleted


class RecordingTrueNative(TrueNativePort):
    """TrueNative fake that records every call it receives."""

    def __init__(self, issuer: str | None = "VISA", fail: bool = False):
        self.issuer = issuer
        self.fail = fail
        self.calls: list[dict] = []

    def register_card(
        self,
        card_number: str,
        expiration_date: str,
        cvv: str,
        card_holder_name: str,
        transaction_identifier: str,
    ) -> TrueNativeRegistration:
        self.calls.append(
            {
                "card_number": card_number,
                "expiration_date": expiration_date,
                "cvv": cvv,
                "card_holder_name": card_holder_name,
                "transaction_identifier": transaction_identifier,
            }
        )
        if self.fail:
            raise TrueNativeRegistrationError("platform on fire")
        return TrueNativeRegistration(
            ruv="ruv-from-platform",
            token="t" * 32,
            issuer=self.issuer,
            transaction_identifier=transaction_identifier,
        )


class RecordingEventPublisher(CardEventPublisherPort):
    """Publisher fake that records every event it receives."""

    def __init__(self):
        self.events: list[dict] = []

    def publish_verification_event(
        self,
        card_id: str,
        ruv: str,
        user_id: str,
        owner_email: str,
        last_four_digits: str,
        issuer: str,
        status: str,
        created_at: str,
    ) -> None:
        self.events.append(
            {
                "card_id": card_id,
                "ruv": ruv,
                "user_id": user_id,
                "owner_email": owner_email,
                "last_four_digits": last_four_digits,
                "issuer": issuer,
                "status": status,
                "created_at": created_at,
            }
        )


def build_use_case(
    repository=None,
    true_native=None,
    event_publisher=None,
) -> tuple[CreateCreditCardUseCase, InMemoryCreditCardRepository, RecordingTrueNative, RecordingEventPublisher]:
    repository = repository if repository is not None else InMemoryCreditCardRepository()
    true_native = true_native if true_native is not None else RecordingTrueNative()
    event_publisher = (
        event_publisher if event_publisher is not None else RecordingEventPublisher()
    )
    use_case = CreateCreditCardUseCase(
        true_native=true_native,
        credit_card_repository=repository,
        card_event_publisher=event_publisher,
    )
    return use_case, repository, true_native, event_publisher


def test_a_valid_request_stores_the_card_as_por_verificar_and_publishes():
    use_case, repository, true_native, event_publisher = build_use_case()

    card = use_case.execute(
        user_id="user-1",
        owner_email="owner@example.com",
        card_number=VALID_CARD_NUMBER,
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    assert card.status is CardStatus.POR_VERIFICAR
    assert card.userId == "user-1"
    assert card.lastFourDigits == "4242"
    assert card.ruv == "ruv-from-platform"
    assert card.token == "t" * 32
    assert card.issuer is CardIssuer.VISA
    assert len(repository.cards) == 1
    assert repository.cards[0] is card
    assert len(event_publisher.events) == 1
    event = event_publisher.events[0]
    assert event["card_id"] == card.id
    assert event["ruv"] == card.ruv
    assert event["user_id"] == "user-1"
    assert event["owner_email"] == "owner@example.com"
    assert event["last_four_digits"] == "4242"
    assert event["issuer"] == "VISA"
    assert event["status"] == "POR_VERIFICAR"
    assert event["created_at"] == card.createdAt.strftime("%Y-%m-%dT%H:%M:%S")


def test_the_truenative_call_carries_the_raw_card_data_once():
    use_case, _, true_native, _ = build_use_case()

    use_case.execute(
        user_id="user-1",
        card_number=VALID_CARD_NUMBER,
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    assert len(true_native.calls) == 1
    call = true_native.calls[0]
    assert call["card_number"] == VALID_CARD_NUMBER
    assert call["cvv"] == VALID_CVV
    assert call["card_holder_name"] == VALID_HOLDER
    assert call["transaction_identifier"]


def test_consecutive_calls_use_distinct_transaction_identifiers():
    use_case, _, true_native, _ = build_use_case()

    use_case.execute(
        user_id="user-1",
        card_number=VALID_CARD_NUMBER,
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )
    use_case.execute(
        user_id="user-1",
        card_number="4111111111111111",
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    identifiers = [call["transaction_identifier"] for call in true_native.calls]
    assert identifiers[0] != identifiers[1]


def test_an_expired_card_is_rejected_before_any_side_effect():
    use_case, repository, true_native, event_publisher = build_use_case()
    now = datetime.now(timezone.utc)
    past_year = now.year - 1

    try:
        use_case.execute(
            user_id="user-1",
            card_number=VALID_CARD_NUMBER,
            cvv=VALID_CVV,
            expiration_date=f"{past_year % 100:02d}/12",
            card_holder_name=VALID_HOLDER,
        )
    except CardExpiredError:
        pass
    else:
        raise AssertionError("CardExpiredError was expected")

    assert repository.cards == []
    assert true_native.calls == []
    assert event_publisher.events == []


def test_a_duplicate_card_for_the_same_user_is_rejected():
    use_case, repository, true_native, event_publisher = build_use_case()
    use_case.execute(
        user_id="user-1",
        card_number=VALID_CARD_NUMBER,
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )
    calls_after_first = len(true_native.calls)

    try:
        use_case.execute(
            user_id="user-1",
            card_number=VALID_CARD_NUMBER,
            cvv=VALID_CVV,
            expiration_date=FAR_FUTURE_EXPIRATION,
            card_holder_name=VALID_HOLDER,
        )
    except DuplicateCreditCardError:
        pass
    else:
        raise AssertionError("DuplicateCreditCardError was expected")

    assert len(repository.cards) == 1
    assert len(true_native.calls) == calls_after_first
    assert len(event_publisher.events) == 1


def test_the_same_card_from_another_user_is_not_a_duplicate():
    use_case, repository, _, _ = build_use_case()
    use_case.execute(
        user_id="user-1",
        card_number=VALID_CARD_NUMBER,
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )
    card = use_case.execute(
        user_id="user-2",
        card_number=VALID_CARD_NUMBER,
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    assert len(repository.cards) == 2
    assert card.userId == "user-2"


def test_a_different_card_from_the_same_user_is_allowed():
    use_case, repository, _, _ = build_use_case()
    use_case.execute(
        user_id="user-1",
        card_number=VALID_CARD_NUMBER,
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )
    card = use_case.execute(
        user_id="user-1",
        card_number="5555555555554444",
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    assert len(repository.cards) == 2
    assert card.lastFourDigits == "4444"


def test_truenative_failure_leaves_nothing_persisted_and_no_event():
    use_case, repository, _, event_publisher = build_use_case(
        true_native=RecordingTrueNative(fail=True)
    )

    try:
        use_case.execute(
            user_id="user-1",
            card_number=VALID_CARD_NUMBER,
            cvv=VALID_CVV,
            expiration_date=FAR_FUTURE_EXPIRATION,
            card_holder_name=VALID_HOLDER,
        )
    except TrueNativeRegistrationError:
        pass
    else:
        raise AssertionError("TrueNativeRegistrationError was expected")

    assert repository.cards == []
    assert event_publisher.events == []


def test_the_issuer_comes_from_the_platform_response():
    use_case, _, _, _ = build_use_case(true_native=RecordingTrueNative("MASTERCARD"))

    card = use_case.execute(
        user_id="user-1",
        card_number="5555555555554444",
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    assert card.issuer is CardIssuer.MASTERCARD


def test_the_platform_issuer_is_normalized_to_the_enum():
    use_case, _, _, _ = build_use_case(true_native=RecordingTrueNative("visa"))

    card = use_case.execute(
        user_id="user-1",
        card_number=VALID_CARD_NUMBER,
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    assert card.issuer is CardIssuer.VISA


def test_an_unknown_platform_issuer_falls_back_to_bin_detection():
    use_case, _, _, _ = build_use_case(
        true_native=RecordingTrueNative("JCB")  # outside the documented enum
    )

    card = use_case.execute(
        user_id="user-1",
        card_number="371449635398431",
        cvv="1234",
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    assert card.issuer is CardIssuer.AMERICAN_EXPRESS


def test_a_missing_platform_issuer_falls_back_to_bin_detection():
    use_case, _, _, _ = build_use_case(true_native=RecordingTrueNative(issuer=None))

    card = use_case.execute(
        user_id="user-1",
        card_number="371449635398431",
        cvv="1234",
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    assert card.issuer is CardIssuer.AMERICAN_EXPRESS


def test_a_missing_issuer_and_an_unrecognized_bin_end_in_unknown():
    use_case, _, _, _ = build_use_case(true_native=RecordingTrueNative(issuer=None))

    card = use_case.execute(
        user_id="user-1",
        card_number="9999999999999999",
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    assert card.issuer is CardIssuer.UNKNOWN


def test_the_stored_dates_honor_the_entity_contract():
    use_case, _, _, _ = build_use_case()

    card = use_case.execute(
        user_id="user-1",
        card_number=VALID_CARD_NUMBER,
        cvv=VALID_CVV,
        expiration_date=FAR_FUTURE_EXPIRATION,
        card_holder_name=VALID_HOLDER,
    )

    now = datetime.now(timezone.utc)
    assert card.createdAt.tzinfo is not None
    assert abs((now - card.createdAt).total_seconds()) < 60
    assert card.updatedAt == card.createdAt
