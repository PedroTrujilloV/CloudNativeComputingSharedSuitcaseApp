"""DynamoDB adapter that updates the terminal status of a card.

The table is owned by the credit_cards_app (3_dynamodb stack); this worker
is the only other component allowed to write it, and it writes only the
status and the updatedAt of the card referenced by the event. Items follow
the storage contract of the owner: a flat map of strings, dates in ISO
yyyy-mm-ddTHH:MM:SS (UTC 0). Credentials are resolved by the standard
boto3 chain (the execution role of the Lambda function); nothing is
hardcoded here.
"""

from datetime import datetime, timezone

import boto3

from config import Settings
from domain.models.card_status import CardStatus
from domain.ports.card_status_repository_port import CardStatusRepositoryPort
from errors import CardNotFoundError

# Date contract of the entity (same as the credit cards application).
ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%S"

# A boto3 DynamoDB client (the boto3.client factory returns it lazily, so
# the annotation stays as a plain comment rather than a runtime type).
_client = None


def build_client(region_name: str | None = None):
    """Create a DynamoDB boto3 client for the configured region."""
    return boto3.client("dynamodb", region_name=region_name or Settings.aws_region)


def get_client():
    """Return the process-wide DynamoDB client (singleton)."""
    global _client
    if _client is None:
        _client = build_client()
    return _client


def reset_client_for_tests() -> None:
    """Drop the singleton client (unit tests only)."""
    global _client
    _client = None


class DynamoDbCardStatusAdapter(CardStatusRepositoryPort):
    """Updates the card status and refreshes updatedAt by card id."""

    def __init__(self, client=None, table_name: str | None = None):
        self.client = client if client is not None else get_client()
        self.table_name = (
            table_name if table_name is not None else Settings.dynamodb_table_name
        )

    def update_status(self, card_id: str, status: CardStatus) -> None:
        current = self._get_item(card_id)
        if current is None:
            raise CardNotFoundError(f"Card {card_id} not found")
        current_status = current.get("status", {}).get("S")
        # Idempotency under the at least once delivery of the queue: a card
        # that already carries this terminal state is not rewritten, so a
        # redelivered event never rewrites the card or its updatedAt.
        if current_status == status.value:
            return
        # Truncate to the storage contract precision (second, UTC 0).
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.client.update_item(
            TableName=self.table_name,
            Key={"id": {"S": card_id}},
            UpdateExpression="SET #st = :status, updatedAt = :updated_at",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":status": {"S": status.value},
                ":updated_at": {"S": now.strftime(ISO_UTC_FORMAT)},
            },
        )

    def _get_item(self, card_id: str) -> dict | None:
        response = self.client.get_item(
            TableName=self.table_name,
            Key={"id": {"S": card_id}},
        )
        return response.get("Item")
