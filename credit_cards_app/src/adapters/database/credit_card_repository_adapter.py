from datetime import datetime, timezone

from domain.models.credit_card import (
    CardIssuer,
    CardStatus,
    CreditCard,
    format_iso_utc,
    parse_iso_utc,
)
from domain.ports.credit_card_repository_port import CreditCardRepositoryPort

# GSI that makes the per owner listing a single DynamoDB query.
USER_INDEX = "userId-index"


class DynamoDbCreditCardRepositoryAdapter(CreditCardRepositoryPort):
    """DynamoDB adapter for the CreditCard entity.

    Every item is stored as a flat map of strings; the dates follow the
    entity contract (ISO yyyy-mm-ddTHH:MM:SS, UTC 0). The raw card number
    and the CVV never reach this layer.
    """

    def __init__(self, table, table_name: str):
        self.table = table
        self.table_name = table_name

    def create(self, card: CreditCard) -> CreditCard:
        self.table.put_item(Item=self._to_item(self._contract_card(card)))
        return self._contract_card(card)

    def get_by_id(self, card_id: str) -> CreditCard | None:
        response = self.table.get_item(Key={"id": card_id})
        item = response.get("Item")
        return self._to_domain(item) if item else None

    def search(self, user_id: str | None = None) -> list[CreditCard]:
        if user_id is not None:
            response = self.table.query(
                IndexName=USER_INDEX,
                KeyConditionExpression="userId = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
            )
        else:
            response = self.table.scan()
        return [self._to_domain(item) for item in response.get("Items", [])]

    def update_status(
        self, card_id: str, status: CardStatus
    ) -> CreditCard | None:
        current = self.get_by_id(card_id)
        if current is None:
            return None
        # Truncate to the storage contract precision (second, UTC 0) so the
        # returned entity matches exactly what is persisted.
        now = datetime.now(timezone.utc).replace(microsecond=0)
        updated = current.model_copy(
            update={
                "status": status,
                "updatedAt": now,
            }
        )
        updated = self._contract_card(updated)
        self.table.put_item(Item=self._to_item(updated))
        return updated

    def count(self) -> int:
        response = self.table.scan(Select="COUNT")
        return response.get("Count", 0)

    def delete_all(self) -> int:
        items = self.table.scan().get("Items", [])
        with self.table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"id": item["id"]})
        return len(items)

    @staticmethod
    def _contract_card(card: CreditCard) -> CreditCard:
        """Project the dates onto the storage contract (UTC, second precision)."""
        return card.model_copy(
            update={
                "createdAt": parse_iso_utc(format_iso_utc(card.createdAt)),
                "updatedAt": parse_iso_utc(format_iso_utc(card.updatedAt)),
            }
        )

    @staticmethod
    def _to_item(card: CreditCard) -> dict:
        return {
            "id": card.id,
            "token": card.token,
            "userId": card.userId,
            "lastFourDigits": card.lastFourDigits,
            "ruv": card.ruv,
            "issuer": card.issuer.value,
            "status": card.status.value,
            "createdAt": format_iso_utc(card.createdAt),
            "updatedAt": format_iso_utc(card.updatedAt),
        }

    @staticmethod
    def _to_domain(item: dict) -> CreditCard:
        return CreditCard(
            id=item["id"],
            token=item["token"],
            userId=item["userId"],
            lastFourDigits=item["lastFourDigits"],
            ruv=item["ruv"],
            issuer=CardIssuer(item["issuer"]),
            status=CardStatus(item["status"]),
            createdAt=parse_iso_utc(item["createdAt"]),
            updatedAt=parse_iso_utc(item["updatedAt"]),
        )
