import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws

from domain.models.credit_card import CardIssuer, CardStatus, CreditCard

# Force the test environment before any Settings read: the pyproject env
# block has no effect without the pytest-env plugin, so the variables are
# set here at runtime (same convention as the other applications).
os.environ["APP_NAME"] = "credit_cards_app"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["DYNAMODB_TABLE_NAME"] = "test_credit_cards"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"

REGION = "us-east-1"
TABLE_NAME = "test_credit_cards"


@pytest.fixture(autouse=True)
def reset_singletons():
    """Drop process wide singletons so every test starts clean."""
    from adapters.database import connection
    from adapters.messaging import card_event_publisher_adapter

    connection.reset_resource_for_tests()
    card_event_publisher_adapter.reset_client_for_tests()
    yield
    connection.reset_resource_for_tests()
    card_event_publisher_adapter.reset_client_for_tests()


@pytest.fixture
def dynamodb_resource():
    """In memory DynamoDB with the same schema as the 3_dynamodb stack."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name=REGION)
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "userId", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "userId-index",
                    "KeySchema": [
                        {"AttributeName": "userId", "KeyType": "HASH"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield boto3.resource("dynamodb", region_name=REGION)


@pytest.fixture
def card_factory():
    """Build valid cards with dates computed at test time (no fixed dates)."""

    def _make_card(**overrides) -> CreditCard:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        data = {
            "id": str(uuid4()),
            "token": "a" * 256,
            "userId": str(uuid4()),
            "lastFourDigits": "4242",
            "ruv": str(uuid4()),
            "issuer": CardIssuer.VISA,
            "status": CardStatus.POR_VERIFICAR,
            "createdAt": now - timedelta(hours=1),
            "updatedAt": now,
        }
        data.update(overrides)
        return CreditCard(**data)

    return _make_card
