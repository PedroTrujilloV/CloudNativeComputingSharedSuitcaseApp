import pytest

from adapters.database.user_repository_adapter import SQLAlchemyUserRepositoryAdapter
from domain.models.user import UserStatus
from errors import TrueNativeRequestError, TrueNativeUnreachableError


def _valid_payload(**overrides):
    payload = {
        "username": "ana_user",
        "password": "Secret123!",
        "email": "ana@example.com",
        "dni": "123456",
        "fullName": "Ana Perez",
        "phoneNumber": "3001234567",
    }
    payload.update(overrides)
    return payload


def _stored_user(db_session, user_id):
    return SQLAlchemyUserRepositoryAdapter(db_session).get_by_id(user_id)


def test_create_user_returns_201_with_id_and_iso_created_at(client):
    response = client.post("/users", json=_valid_payload())

    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"id", "createdAt"}
    assert body["id"]
    assert "T" in body["createdAt"]
    assert len(body["createdAt"]) == 19


def test_create_user_missing_required_field_returns_400(client):
    payload = _valid_payload()
    del payload["email"]

    response = client.post("/users", json=payload)

    assert response.status_code == 400


def test_create_user_malformed_email_returns_400(client):
    response = client.post("/users", json=_valid_payload(email="not-an-email"))

    assert response.status_code == 400


def test_create_user_malformed_username_returns_400(client):
    response = client.post("/users", json=_valid_payload(username="ana user"))

    assert response.status_code == 400


def test_create_user_duplicate_username_returns_412(client):
    client.post("/users", json=_valid_payload())
    response = client.post(
        "/users",
        json=_valid_payload(email="other@example.com"),
    )

    assert response.status_code == 412


def test_create_user_duplicate_email_returns_412(client):
    client.post("/users", json=_valid_payload())
    response = client.post(
        "/users",
        json=_valid_payload(username="other_user"),
    )

    assert response.status_code == 412


def test_create_user_does_not_echo_password(client):
    response = client.post("/users", json=_valid_payload())

    assert response.status_code == 201
    assert "password" not in response.json()


def test_create_user_stores_por_verificar_with_ruv(
    client, db_session, verification_provider
):
    response = client.post("/users", json=_valid_payload())

    body = response.json()
    stored = _stored_user(db_session, body["id"])

    assert response.status_code == 201
    assert stored.status == UserStatus.POR_VERIFICAR
    assert stored.ruv is not None
    assert (
        stored.ruv == f"ruv-{verification_provider.calls[0]['transaction_identifier']}"
    )


def test_create_user_sends_available_fields_to_provider(
    client, db_session, verification_provider
):
    response = client.post("/users", json=_valid_payload())
    body = response.json()

    assert len(verification_provider.calls) == 1
    call = verification_provider.calls[0]
    assert call["user_identifier"] == body["id"]
    assert call["transaction_identifier"]
    sent = call["user"]
    assert sent.username == "ana_user"
    assert sent.email == "ana@example.com"
    assert sent.dni == "123456"
    assert sent.fullName == "Ana Perez"
    assert sent.phoneNumber == "3001234567"


def test_create_user_uses_unique_transaction_identifier_per_request(
    client, verification_provider
):
    client.post("/users", json=_valid_payload())
    client.post(
        "/users",
        json=_valid_payload(username="other_user", email="other@example.com"),
    )

    identifiers = [
        call["transaction_identifier"] for call in verification_provider.calls
    ]

    assert len(identifiers) == 2
    assert identifiers[0] != identifiers[1]


@pytest.mark.parametrize("status_code", [400, 401, 403, 409, 500])
def test_create_user_with_provider_rejection_stores_no_verificado(
    client, db_session, verification_provider, status_code
):
    verification_provider.error = TrueNativeRequestError(status_code, "rejected")

    response = client.post("/users", json=_valid_payload())

    assert response.status_code == 201
    assert len(verification_provider.calls) == 1
    stored = _stored_user(db_session, response.json()["id"])
    assert stored.status == UserStatus.NO_VERIFICADO
    assert stored.ruv is None


def test_create_user_with_unreachable_provider_stores_no_verificado(
    client, db_session, verification_provider
):
    verification_provider.error = TrueNativeUnreachableError("connection refused")

    response = client.post("/users", json=_valid_payload())

    assert response.status_code == 201
    assert len(verification_provider.calls) == 1
    stored = _stored_user(db_session, response.json()["id"])
    assert stored.status == UserStatus.NO_VERIFICADO
    assert stored.ruv is None
