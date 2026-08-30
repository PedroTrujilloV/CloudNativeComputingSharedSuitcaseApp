def test_ping_returns_pong(client):
    """GET /users/ping should return 200 with body pong."""
    response = client.get("/users/ping")

    assert response.status_code == 200
    assert response.text == "pong"
