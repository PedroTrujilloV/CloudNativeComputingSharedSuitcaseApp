def _create_and_auth(client):
    create_response = client.post(
        "/users",
        json={
            "username": "ana_user",
            "password": "Secret123!",
            "email": "ana@example.com",
            "dni": "123456",
            "fullName": "Ana Perez",
            "phoneNumber": "3001234567",
        },
    )
    assert create_response.status_code == 201

    auth_response = client.post(
        "/users/auth",
        json={"username": "ana_user", "password": "Secret123!"},
    )
    assert auth_response.status_code == 200
    return create_response.json(), auth_response.json()


def test_get_me_returns_200_profile(client):
    created, auth = _create_and_auth(client)

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {auth['token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "id",
        "username",
        "email",
        "fullName",
        "dni",
        "phoneNumber",
        "status",
    }
    assert body["id"] == created["id"]
    assert body["username"] == "ana_user"
    assert body["email"] == "ana@example.com"
    assert body["fullName"] == "Ana Perez"
    assert body["dni"] == "123456"
    assert body["phoneNumber"] == "3001234567"
    assert body["status"] == "POR_VERIFICAR"
    assert "password" not in body
    assert "token" not in body


def test_get_me_without_token_returns_403(client):
    response = client.get("/users/me")

    assert response.status_code == 403


def test_get_me_with_invalid_token_returns_401(client):
    _, auth = _create_and_auth(client)

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {auth['token']}fake"},
    )

    assert response.status_code == 401
