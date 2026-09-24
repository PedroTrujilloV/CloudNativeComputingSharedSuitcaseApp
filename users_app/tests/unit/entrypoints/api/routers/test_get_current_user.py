def _mark_verified(client, user_id, status="VERIFICADO"):
    """Apply a verification status the way the callback component does."""
    response = client.patch(f"/users/{user_id}", json={"status": status})
    assert response.status_code == 200
    return response


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
    _mark_verified(client, create_response.json()["id"])

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
    assert body["status"] == "VERIFICADO"
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


def test_get_me_rejects_token_of_user_who_is_no_longer_verified(client):
    """A token issued while the user was VERIFICADO stops resolving once
    the status leaves that state (RF-007 token verification gate)."""
    created, auth = _create_and_auth(client)
    _mark_verified(client, created["id"], status="NO_VERIFICADO")

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {auth['token']}"},
    )

    assert response.status_code == 401
