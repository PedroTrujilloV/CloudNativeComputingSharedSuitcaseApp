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


def test_count_users_returns_zero_when_empty(client):
    response = client.get("/users/count")

    assert response.status_code == 200
    assert response.json() == {"count": 0}


def test_count_users_returns_number_of_created_users(client):
    _create_user(client, username="ana_user", email="ana@example.com")
    _create_user(client, username="bob_user", email="bob@example.com")

    response = client.get("/users/count")

    assert response.status_code == 200
    assert response.json() == {"count": 2}
