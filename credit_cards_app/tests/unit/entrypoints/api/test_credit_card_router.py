import json
import re
import time
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from adapters.database.credit_card_repository_adapter import (
    DynamoDbCreditCardRepositoryAdapter,
)
from domain.models.verified_user import VerifiedUser
from domain.ports.card_event_publisher_port import CardEventPublisherPort
from domain.ports.true_native_port import (
    TrueNativePort,
    TrueNativeRegistration,
)
from domain.ports.user_token_verification_port import UserTokenVerificationPort
from entrypoints.api import deps
from entrypoints.api.main import app
from errors import (
    InvalidTokenError,
    TrueNativeRegistrationError,
    UserVerificationUnavailableError,
)

VALID_PAYLOAD = {
    "cardNumber": "4242424242424242",
    "cvv": "123",
    "expirationDate": "28/01",
    "cardHolderName": "Jane Doe",
}


class FakeUserVerification(UserTokenVerificationPort):
    """Verification fake driven by the token value itself.

    Every token resolves to user-1 by default; the token "token-user-2"
    resolves to a second user, which lets the tests check the user
    scoped filtering of the listing endpoint.
    """

    def __init__(self, unavailable_tokens=()):
        self.unavailable_tokens = set(unavailable_tokens)

    def verify(self, token: str) -> VerifiedUser:
        if token in self.unavailable_tokens:
            raise UserVerificationUnavailableError()
        if token == "invalid-token":
            raise InvalidTokenError()
        if token == "token-user-2":
            return VerifiedUser(id="user-2", email="second@example.com")
        return VerifiedUser(id="user-1", email="owner@example.com")


class FakeTrueNative(TrueNativePort):
    """Tokenization fake that records the calls and can fail on demand."""

    def __init__(self, fail: bool = False, issuer: str | None = "VISA"):
        self.fail = fail
        self.issuer = issuer
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
                "cvv": cvv,
                "transaction_identifier": transaction_identifier,
            }
        )
        if self.fail:
            raise TrueNativeRegistrationError()
        return TrueNativeRegistration(
            ruv="ruv-from-platform",
            token="p" * 32,
            issuer=self.issuer,
            transaction_identifier=transaction_identifier,
        )


class FakeEventPublisher(CardEventPublisherPort):
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
                "issuer": issuer,
                "status": status,
                "created_at": created_at,
            }
        )


@pytest.fixture
def fake_user_verification():
    return FakeUserVerification()


@pytest.fixture
def fake_true_native():
    return FakeTrueNative()


@pytest.fixture
def fake_event_publisher():
    return FakeEventPublisher()


@pytest.fixture
def dynamodb_repository(dynamodb_resource):
    """The real DynamoDB adapter over the moto in memory table."""
    table = dynamodb_resource.Table("test_credit_cards")
    return DynamoDbCreditCardRepositoryAdapter(
        table=table, table_name="test_credit_cards"
    )


@pytest.fixture
def client(
    fake_user_verification,
    fake_true_native,
    fake_event_publisher,
    dynamodb_repository,
):
    """TestClient with the outbound ports replaced by fakes.

    The use case, the router, the schemas, and the DynamoDB adapter stay
    real; only the users application, TrueNative, and the queue are faked.
    """
    app.dependency_overrides[deps.get_user_verification] = lambda: fake_user_verification
    app.dependency_overrides[deps.get_true_native] = lambda: fake_true_native
    app.dependency_overrides[deps.get_card_event_publisher] = (
        lambda: fake_event_publisher
    )
    app.dependency_overrides[deps.get_credit_card_repository] = (
        lambda: dynamodb_repository
    )
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def post(client, payload=None, token=None):
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.post("/credit-cards", json=payload if payload is not None else {}, headers=headers)


def get(client, token=None):
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.get("/credit-cards", headers=headers)


def test_a_valid_request_returns_201_with_the_creation_payload(client, fake_true_native, fake_event_publisher):
    started = time.monotonic()
    response = post(client, VALID_PAYLOAD, token="valid-token")
    elapsed = time.monotonic() - started

    assert response.status_code == 201
    assert elapsed < 5
    body = response.json()
    assert set(body) == {"id", "userId", "createdAt"}
    assert body["userId"] == "user-1"
    # The creation date honors the entity contract (ISO, UTC, seconds).
    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", body["createdAt"]
    )
    # The id is a UUID, as documented.
    UUID(body["id"])


def test_the_card_is_persisted_as_por_verificar_without_raw_data(
    client, dynamodb_repository
):
    response = post(client, VALID_PAYLOAD, token="valid-token")
    card_id = response.json()["id"]

    stored = dynamodb_repository.get_by_id(card_id)
    assert stored is not None
    assert stored.status.value == "POR_VERIFICAR"
    assert stored.userId == "user-1"
    assert stored.lastFourDigits == "4242"
    assert stored.ruv == "ruv-from-platform"
    assert stored.issuer.value == "VISA"
    assert stored.token == "p" * 32
    # The raw card number and the CVV never reach the storage layer.
    item = dynamodb_repository.table.get_item(Key={"id": card_id})["Item"]
    assert "cardNumber" not in item
    assert "cvv" not in item
    assert "4242424242424242" not in json.dumps(item)


def test_the_verification_event_is_published_after_the_persist(client, fake_event_publisher):
    response = post(client, VALID_PAYLOAD, token="valid-token")

    assert len(fake_event_publisher.events) == 1
    event = fake_event_publisher.events[0]
    assert event["card_id"] == response.json()["id"]
    assert event["ruv"] == "ruv-from-platform"
    assert event["user_id"] == "user-1"
    assert event["owner_email"] == "owner@example.com"
    assert event["status"] == "POR_VERIFICAR"
    assert event["created_at"] == response.json()["createdAt"]


def test_the_truenative_call_uses_a_unique_transaction_identifier(client, fake_true_native):
    post(client, VALID_PAYLOAD, token="valid-token")
    post(
        client,
        {**VALID_PAYLOAD, "cardNumber": "4111111111111111"},
        token="valid-token",
    )

    identifiers = [call["transaction_identifier"] for call in fake_true_native.calls]
    assert len(identifiers) == 2
    assert identifiers[0] != identifiers[1]


def test_a_request_without_token_returns_403(client):
    assert post(client, VALID_PAYLOAD, token=None).status_code == 403
    assert post(client, VALID_PAYLOAD, token="").status_code == 403


def test_an_invalid_token_returns_401(client):
    assert post(client, VALID_PAYLOAD, token="invalid-token").status_code == 401


def test_a_non_bearer_scheme_returns_401(client):
    response = client.post(
        "/credit-cards",
        json=VALID_PAYLOAD,
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 401


def test_the_users_application_failure_returns_502(client, fake_user_verification):
    fake_user_verification.unavailable_tokens.add("down-token")

    assert post(client, VALID_PAYLOAD, token="down-token").status_code == 502


def test_missing_fields_return_400(client):
    for missing_field in VALID_PAYLOAD:
        payload = {key: value for key, value in VALID_PAYLOAD.items() if key != missing_field}
        assert post(client, payload, token="valid-token").status_code == 400


@pytest.mark.parametrize(
    "override",
    [
        {"cardNumber": "424242424242424x"},  # not digits
        {"cardNumber": "123"},  # too short
        {"cvv": "12"},  # too short
        {"cvv": "12345"},  # too long
        {"expirationDate": "01/28"},  # month first is malformed
        {"expirationDate": "28/13"},  # impossible month
        {"expirationDate": "2801"},  # missing separator
        {"cardHolderName": "   "},  # blank
        {"cardHolderName": ""},  # empty
    ],
)
def test_malformed_fields_return_400(client, override):
    payload = {**VALID_PAYLOAD, **override}
    assert post(client, payload, token="valid-token").status_code == 400


def test_an_expired_card_returns_412(client, fake_true_native, dynamodb_repository):
    year = datetime.now(timezone.utc).year - 2
    payload = {**VALID_PAYLOAD, "expirationDate": f"{year % 100:02d}/12"}

    assert post(client, payload, token="valid-token").status_code == 412
    assert fake_true_native.calls == []
    assert dynamodb_repository.count() == 0


def test_a_duplicate_card_returns_409(client, fake_true_native, dynamodb_repository):
    assert post(client, VALID_PAYLOAD, token="valid-token").status_code == 201

    response = post(client, VALID_PAYLOAD, token="valid-token")

    assert response.status_code == 409
    assert len(fake_true_native.calls) == 1
    assert dynamodb_repository.count() == 1


def test_truenative_failure_returns_502_and_stores_nothing(
    client, fake_true_native, fake_event_publisher, dynamodb_repository
):
    fake_true_native.fail = True

    assert post(client, VALID_PAYLOAD, token="valid-token").status_code == 502
    assert dynamodb_repository.count() == 0
    assert fake_event_publisher.events == []


def test_the_listing_returns_only_the_cards_of_the_caller(client):
    payload_two = {
        "cardNumber": "4111111111111111",
        "cvv": "123",
        "expirationDate": "28/01",
        "cardHolderName": "John Doe",
    }
    card_one_id = post(client, VALID_PAYLOAD, token="valid-token").json()["id"]
    card_two_id = post(client, payload_two, token="token-user-2").json()["id"]

    response = get(client, token="valid-token")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    card = body[0]
    # The item carries exactly the documented contract fields.
    assert set(card) == {
        "id",
        "token",
        "userId",
        "lastFourDigits",
        "issuer",
        "status",
        "createdAt",
        "updatedAt",
    }
    assert card["id"] == card_one_id
    assert card["userId"] == "user-1"
    assert card["token"] == "p" * 32
    assert card["lastFourDigits"] == "4242"
    assert card["issuer"] == "VISA"
    assert card["status"] == "POR_VERIFICAR"
    # The dates honor the entity contract (ISO, UTC, seconds).
    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", card["createdAt"]
    )
    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", card["updatedAt"]
    )


def test_the_listing_never_returns_the_cards_of_another_user(client):
    payload_two = {
        "cardNumber": "4111111111111111",
        "cvv": "123",
        "expirationDate": "28/01",
        "cardHolderName": "John Doe",
    }
    post(client, VALID_PAYLOAD, token="valid-token")
    post(client, payload_two, token="token-user-2")

    response = get(client, token="token-user-2")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["userId"] == "user-2"
    assert body[0]["lastFourDigits"] == "1111"
    assert body[0]["token"] == "p" * 32


def test_the_listing_returns_an_empty_array_when_the_caller_has_no_cards(client):
    response = get(client, token="valid-token")

    assert response.status_code == 200
    assert response.json() == []


def test_the_listing_without_a_token_returns_403(client):
    assert get(client).status_code == 403


def test_the_listing_with_an_invalid_token_returns_401(client):
    assert get(client, token="invalid-token").status_code == 401


def test_the_listing_with_a_non_bearer_scheme_returns_401(client):
    response = client.get(
        "/credit-cards", headers={"Authorization": "Basic valid-token"}
    )
    assert response.status_code == 401


def test_the_ping_answers_pong_without_a_token(client):
    response = client.get("/credit-cards/ping")

    assert response.status_code == 200
    # The contract is the plain text pong, not a JSON string.
    assert response.text == "pong"
    assert "text/plain" in response.headers["content-type"]


def test_the_count_answers_without_a_token_and_reflects_the_table(client):
    assert client.get("/credit-cards/count").json() == {"count": 0}

    payload_two = {
        "cardNumber": "4111111111111111",
        "cvv": "123",
        "expirationDate": "28/01",
        "cardHolderName": "John Doe",
    }
    post(client, VALID_PAYLOAD, token="valid-token")
    post(client, payload_two, token="token-user-2")

    assert client.get("/credit-cards/count").json() == {"count": 2}


def test_the_reset_deletes_every_card_without_a_token(client):
    payload_two = {
        "cardNumber": "4111111111111111",
        "cvv": "123",
        "expirationDate": "28/01",
        "cardHolderName": "John Doe",
    }
    post(client, VALID_PAYLOAD, token="valid-token")
    post(client, payload_two, token="token-user-2")

    response = client.post("/credit-cards/reset")

    assert response.status_code == 200
    # The exact documented message string, not translated.
    assert response.json() == {"msg": "Todos los datos fueron eliminados"}
    assert client.get("/credit-cards/count").json() == {"count": 0}
    assert get(client, token="valid-token").json() == []
    assert get(client, token="token-user-2").json() == []


def test_the_reset_on_an_empty_table_returns_the_same_message(client):
    response = client.post("/credit-cards/reset")

    assert response.status_code == 200
    assert response.json() == {"msg": "Todos los datos fueron eliminados"}
