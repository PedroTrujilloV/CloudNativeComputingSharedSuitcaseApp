from adapters.database.models import UserModel


def _create_user(client, **overrides):
    payload = {
        "username": "ana_user",
        "password": "Secret123!",
        "email": "ana@example.com",
        "dni": "123456",
        "fullName": "Ana Perez",
        "phoneNumber": "3001234567",
    }
    payload.update(overrides)
    return client.post("/users", json=payload)


def _mark_verified(client, user_id, status="VERIFICADO"):
    """Apply a verification status the way the callback component does."""
    response = client.patch(f"/users/{user_id}", json={"status": status})
    assert response.status_code == 200
    return response


def test_authenticate_user_returns_200_with_id_token_and_expire_at(client):
    create_response = _create_user(client)
    assert create_response.status_code == 201
    _mark_verified(client, create_response.json()["id"])

    response = client.post(
        "/users/auth",
        json={"username": "ana_user", "password": "Secret123!"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"id", "token", "expireAt"}
    assert body["id"] == create_response.json()["id"]
    assert body["token"]
    assert "." not in body["token"]  # opaque token, not JWT
    assert "T" in body["expireAt"]
    assert len(body["expireAt"]) == 19


def test_authenticate_user_por_verificar_returns_401(client, db_session):
    create_response = _create_user(client)
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    response = client.post(
        "/users/auth",
        json={"username": "ana_user", "password": "Secret123!"},
    )

    assert response.status_code == 401
    assert response.text == ""
    stored = db_session.get(UserModel, user_id)
    assert stored.status == "POR_VERIFICAR"
    assert stored.token is None
    assert stored.expireAt is None


def test_authenticate_user_no_verificado_returns_401(client, db_session):
    create_response = _create_user(client)
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]
    _mark_verified(client, user_id, status="NO_VERIFICADO")

    response = client.post(
        "/users/auth",
        json={"username": "ana_user", "password": "Secret123!"},
    )

    assert response.status_code == 401
    stored = db_session.get(UserModel, user_id)
    assert stored.status == "NO_VERIFICADO"
    assert stored.token is None
    assert stored.expireAt is None


def test_authenticate_user_wrong_password_returns_404(client):
    assert _create_user(client).status_code == 201

    response = client.post(
        "/users/auth",
        json={"username": "ana_user", "password": "WrongPassword!"},
    )

    assert response.status_code == 404


def test_authenticate_user_unknown_username_returns_404(client):
    response = client.post(
        "/users/auth",
        json={"username": "missing_user", "password": "Secret123!"},
    )

    assert response.status_code == 404


def test_authenticate_user_missing_password_returns_400(client):
    response = client.post("/users/auth", json={"username": "ana_user"})

    assert response.status_code == 400


def test_authenticate_user_missing_username_returns_400(client):
    response = client.post("/users/auth", json={"password": "Secret123!"})

    assert response.status_code == 400
