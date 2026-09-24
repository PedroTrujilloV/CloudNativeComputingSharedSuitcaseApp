from fastapi import FastAPI
from fastapi.testclient import TestClient

from entrypoints.api.main import app


def test_app_is_a_fastapi_application():
    assert isinstance(app, FastAPI)


def test_app_title_comes_from_the_settings():
    assert app.title == "credit_cards_app"


def test_the_business_routes_are_exposed():
    """Every business endpoint of the RF-006 API is exposed, with and
    without the trailing slash variant."""
    business_paths = {
        route.path for route in _business_routes() if "/credit-cards" in route.path
    }
    assert business_paths == {
        "/credit-cards",
        "/credit-cards/",
        "/credit-cards/count",
        "/credit-cards/count/",
        "/credit-cards/ping",
        "/credit-cards/ping/",
        "/credit-cards/reset",
        "/credit-cards/reset/",
    }


def _business_routes():
    """Flatten the routes, including the ones held by the included router."""
    from entrypoints.api.routers.credit_card_router import router

    return list(router.routes) + [
        route
        for route in app.routes
        if hasattr(route, "path") and "credit-cards" in route.path
    ]


def test_lifespan_starts_without_a_reachable_dynamodb():
    """The startup only logs; it must not require the database."""
    with TestClient(app) as test_client:
        response = test_client.get("/openapi.json")
    assert response.status_code == 200


def test_the_utility_endpoints_are_served_without_authentication(
    dynamodb_resource, card_factory
):
    """The utility endpoints need no bearer token.

    The count and reset use the real repository over the moto in memory
    table (no dependency overrides in this module); the cards are stored
    through the repository itself, the way the creation flow stores them.
    """
    from adapters.database.credit_card_repository_adapter import (
        DynamoDbCreditCardRepositoryAdapter,
    )

    repository = DynamoDbCreditCardRepositoryAdapter(
        table=dynamodb_resource.Table("test_credit_cards"),
        table_name="test_credit_cards",
    )

    with TestClient(app) as test_client:
        ping = test_client.get("/credit-cards/ping")
        assert ping.status_code == 200
        assert ping.text == "pong"

        count = test_client.get("/credit-cards/count")
        assert count.status_code == 200
        assert count.json() == {"count": 0}

        # Two stored cards (the way the creation flow stores them).
        repository.create(card_factory())
        repository.create(card_factory())
        assert test_client.get("/credit-cards/count").json() == {"count": 2}

        reset = test_client.post("/credit-cards/reset")
        assert reset.status_code == 200
        assert reset.json() == {"msg": "Todos los datos fueron eliminados"}

        assert test_client.get("/credit-cards/count").json() == {"count": 0}
        assert test_client.get("/credit-cards").status_code == 403
