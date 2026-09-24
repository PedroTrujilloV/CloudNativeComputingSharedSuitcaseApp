import json

import httpx2
import pytest

from adapters.truenative.true_native_adapter import HttpTrueNativeAdapter
from errors import TrueNativeRegistrationError

BASE_URL = "http://truenative.test"
SECRET = "the-secret-token"


def build_adapter(handler) -> HttpTrueNativeAdapter:
    transport = httpx2.MockTransport(handler)
    return HttpTrueNativeAdapter(
        base_url=BASE_URL,
        secret_token=SECRET,
        client_factory=lambda: httpx2.Client(transport=transport),
    )


def handler_returning(status_code: int, body):
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url.path == "/native/cards"
        return httpx2.Response(status_code, json=body, request=request)

    return handler


def test_a_successful_registration_returns_ruv_token_and_issuer():
    adapter = build_adapter(
        handler_returning(
            201,
            {
                "RUV": "ruv-1",
                "token": "token-1",
                "issuer": "VISA",
                "task_status": "ACCEPTED",
            },
        )
    )

    registration = adapter.register_card(
        card_number="4242424242424242",
        expiration_date="28/01",
        cvv="123",
        card_holder_name="Jane Doe",
        transaction_identifier="tx-1",
    )

    assert registration.ruv == "ruv-1"
    assert registration.token == "token-1"
    assert registration.issuer == "VISA"
    assert registration.transaction_identifier == "tx-1"


def test_the_request_carries_the_card_object_and_the_secret_token():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            201,
            json={"RUV": "ruv-1", "token": "token-1", "issuer": "VISA"},
            request=request,
        )

    adapter = build_adapter(handler)
    adapter.register_card(
        card_number="4242424242424242",
        expiration_date="28/01",
        cvv="123",
        card_holder_name="Jane Doe",
        transaction_identifier="tx-1",
    )

    assert seen["authorization"] == f"Bearer {SECRET}"
    body = seen["body"]
    assert body["transactionIdentifier"] == "tx-1"
    assert body["card"]["cardNumber"] == "4242424242424242"
    assert body["card"]["cvv"] == "123"
    assert body["card"]["cardHolderName"] == "Jane Doe"
    # The platform contract normalizes the client YY/MM input to MM/YYYY.
    assert body["card"]["expirationDate"] == "01/2028"


def test_an_unauthorized_registration_raises():
    adapter = build_adapter(handler_returning(401, {"message": "bad secret"}))

    with pytest.raises(TrueNativeRegistrationError):
        adapter.register_card(
            card_number="4242424242424242",
            expiration_date="28/01",
            cvv="123",
            card_holder_name="Jane Doe",
            transaction_identifier="tx-1",
        )


def test_a_verification_already_in_progress_raises():
    adapter = build_adapter(handler_returning(409, {"message": "in progress"}))

    with pytest.raises(TrueNativeRegistrationError):
        adapter.register_card(
            card_number="4242424242424242",
            expiration_date="28/01",
            cvv="123",
            card_holder_name="Jane Doe",
            transaction_identifier="tx-1",
        )


def test_a_malformed_request_raises():
    adapter = build_adapter(handler_returning(400, {"message": "malformed"}))

    with pytest.raises(TrueNativeRegistrationError):
        adapter.register_card(
            card_number="4242424242424242",
            expiration_date="28/01",
            cvv="123",
            card_holder_name="Jane Doe",
            transaction_identifier="tx-1",
        )


def test_a_platform_failure_raises():
    adapter = build_adapter(handler_returning(500, {"message": "boom"}))

    with pytest.raises(TrueNativeRegistrationError):
        adapter.register_card(
            card_number="4242424242424242",
            expiration_date="28/01",
            cvv="123",
            card_holder_name="Jane Doe",
            transaction_identifier="tx-1",
        )


def test_an_answer_missing_the_ruv_raises():
    adapter = build_adapter(handler_returning(201, {"token": "token-1"}))

    with pytest.raises(TrueNativeRegistrationError):
        adapter.register_card(
            card_number="4242424242424242",
            expiration_date="28/01",
            cvv="123",
            card_holder_name="Jane Doe",
            transaction_identifier="tx-1",
        )


def test_an_answer_missing_the_token_raises():
    adapter = build_adapter(handler_returning(201, {"RUV": "ruv-1"}))

    with pytest.raises(TrueNativeRegistrationError):
        adapter.register_card(
            card_number="4242424242424242",
            expiration_date="28/01",
            cvv="123",
            card_holder_name="Jane Doe",
            transaction_identifier="tx-1",
        )


def test_an_answer_without_an_issuer_keeps_it_optional():
    adapter = build_adapter(
        handler_returning(201, {"RUV": "ruv-1", "token": "token-1"})
    )

    registration = adapter.register_card(
        card_number="4242424242424242",
        expiration_date="28/01",
        cvv="123",
        card_holder_name="Jane Doe",
        transaction_identifier="tx-1",
    )

    assert registration.issuer is None


def test_an_unparseable_answer_raises():
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            201, content=b"not json", request=request, headers={"Content-Type": "text/plain"}
        )

    adapter = build_adapter(handler)

    with pytest.raises(TrueNativeRegistrationError):
        adapter.register_card(
            card_number="4242424242424242",
            expiration_date="28/01",
            cvv="123",
            card_holder_name="Jane Doe",
            transaction_identifier="tx-1",
        )


def test_a_network_failure_raises():
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused")

    adapter = build_adapter(handler)

    with pytest.raises(TrueNativeRegistrationError):
        adapter.register_card(
            card_number="4242424242424242",
            expiration_date="28/01",
            cvv="123",
            card_holder_name="Jane Doe",
            transaction_identifier="tx-1",
        )
