def _create_user(client, *, username: str, email: str):
    response = client.post(
        "/users",
        json={
            "username": username,
            "password": "Secret123!",
            "email": email,
        },
    )
    assert response.status_code == 201


def test_reset_users_returns_confirmation_message(client):
    response = client.post("/users/reset")

    assert response.status_code == 200
    assert response.json() == {"msg": "Todos los datos fueron eliminados"}


def test_reset_users_deletes_all_users(client):
    _create_user(client, username="ana_user", email="ana@example.com")
    _create_user(client, username="bob_user", email="bob@example.com")
    assert client.get("/users/count").json()["count"] == 2

    reset = client.post("/users/reset")

    assert reset.status_code == 200
    assert client.get("/users/count").json() == {"count": 0}
