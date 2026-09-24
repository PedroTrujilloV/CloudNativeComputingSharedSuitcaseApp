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
    response = client.post("/users", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_update_user_returns_200_and_confirmation_message(client):
    user_id = _create_user(client)

    response = client.patch(
        f"/users/{user_id}",
        json={
            "status": "VERIFICADO",
            "dni": "999888",
            "fullName": "Ana Updated",
            "phoneNumber": "3110000000",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["msg"] == "el usuario ha sido actualizado"
    # The updated user record is returned so the internal caller (the
    # verification callback) can build the result email from the data the
    # platform persists.
    user = body["user"]
    assert user["id"] == user_id
    assert user["username"] == "ana_user"
    assert user["email"] == "ana@example.com"
    assert user["dni"] == "999888"
    assert user["fullName"] == "Ana Updated"
    assert user["phoneNumber"] == "3110000000"
    assert user["status"] == "VERIFICADO"
    # The test fake TrueNative provider stores a RUV at creation time.
    assert user["ruv"] is not None
    assert user["updatedAt"] is not None


def test_update_user_persists_changes_visible_via_me(client):
    user_id = _create_user(client)
    client.patch(
        f"/users/{user_id}",
        json={"fullName": "Ana Updated", "status": "VERIFICADO"},
    )

    auth = client.post(
        "/users/auth",
        json={"username": "ana_user", "password": "Secret123!"},
    )
    token = auth.json()["token"]
    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["fullName"] == "Ana Updated"
    assert me.json()["status"] == "VERIFICADO"


def test_update_user_unknown_id_returns_404(client):
    response = client.patch(
        "/users/00000000-0000-0000-0000-000000000099",
        json={"fullName": "Nobody"},
    )

    assert response.status_code == 404


def test_update_user_empty_body_returns_400(client):
    user_id = _create_user(client)

    response = client.patch(f"/users/{user_id}", json={})

    assert response.status_code == 400


def test_update_user_only_disallowed_fields_returns_400(client):
    user_id = _create_user(client)

    response = client.patch(
        f"/users/{user_id}",
        json={"username": "hacked", "email": "hacked@example.com"},
    )

    assert response.status_code == 400


def test_update_user_invalid_status_returns_400(client):
    user_id = _create_user(client)

    response = client.patch(
        f"/users/{user_id}",
        json={"status": "NOT_A_STATUS"},
    )

    assert response.status_code == 400


def test_update_user_partial_update_does_not_require_auth(client):
    user_id = _create_user(client)

    # Public endpoint: no Authorization header.
    response = client.patch(
        f"/users/{user_id}",
        json={"phoneNumber": "3009998877"},
    )

    assert response.status_code == 200
    assert response.json()["msg"] == "el usuario ha sido actualizado"
