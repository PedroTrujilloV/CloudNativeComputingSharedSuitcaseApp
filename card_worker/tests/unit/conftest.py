import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws

# Force the test environment before any Settings read: the pyproject env
# block has no effect without the pytest-env plugin, so the variables are
# set here at runtime (same convention as the other applications).
os.environ["APP_NAME"] = "card_worker"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["DYNAMODB_TABLE_NAME"] = "test_credit_cards"
os.environ["TRUENATIVE_URL"] = "http://truenative.test"
os.environ["TRUENATIVE_SECRET_TOKEN"] = "test-secret-token"
os.environ["CARD_RESULT_TOPIC_ARN"] = ""
# The unit tests keep the polling loop deterministic (the wait between
# attempts is injected and recorded, never executed).
os.environ["POLL_MAX_ATTEMPTS"] = "3"
os.environ["POLL_INTERVAL_SECONDS"] = "0"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"

REGION = "us-east-1"

# Date contract of the entity: ISO yyyy-mm-ddTHH:MM:SS, UTC 0.
ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%S"


def iso_now(offset_seconds: int = 0) -> str:
    """Build a contract date computed at test time (no fixed dates)."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return (now + timedelta(seconds=offset_seconds)).strftime(ISO_UTC_FORMAT)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Drop process wide singletons so every test starts clean."""
    from adapters.database import credit_card_status_adapter

    credit_card_status_adapter.reset_client_for_tests()
    yield
    credit_card_status_adapter.reset_client_for_tests()


@pytest.fixture
def dynamodb_client():
    """In memory DynamoDB with the same schema as the 3_dynamodb stack."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name=REGION)
        client.create_table(
            TableName="test_credit_cards",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "userId", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "userId-index",
                    "KeySchema": [{"AttributeName": "userId", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield client


@pytest.fixture
def card_store(dynamodb_client):
    """Helpers to store and read flat string items as the owner writes them."""

    class CardStore:
        table_name = "test_credit_cards"

        def put(self, card_id: str, status: str = "POR_VERIFICAR") -> dict:
            item = {
                "id": {"S": card_id},
                "token": {"S": "a" * 256},
                "userId": {"S": str(uuid4())},
                "lastFourDigits": {"S": "4242"},
                "ruv": {"S": str(uuid4())},
                "issuer": {"S": "VISA"},
                "status": {"S": status},
                "createdAt": {"S": iso_now(-3600)},
                # The last update is one hour in the past, so any refresh
                # written by the adapter (now, second precision) is always
                # different, no matter when the test runs.
                "updatedAt": {"S": iso_now(-3600)},
            }
            dynamodb_client.put_item(TableName=self.table_name, Item=item)
            return item

        def get(self, card_id: str) -> dict:
            response = dynamodb_client.get_item(
                TableName=self.table_name,
                Key={"id": {"S": card_id}},
            )
            return response["Item"]

    return CardStore()
