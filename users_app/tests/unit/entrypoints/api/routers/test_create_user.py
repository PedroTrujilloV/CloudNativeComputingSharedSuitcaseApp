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
