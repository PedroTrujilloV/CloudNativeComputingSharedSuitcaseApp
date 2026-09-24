# DynamoDB table for the CreditCard entity of the credit_cards_app.
#
# The table is exclusive to the credit cards application: no other component
# of the platform creates it, and no other application reads from it except
# the card worker, which talks to the same DynamoDB API. That is what makes
# the storage of RF-006 decoupled from the shared PostgreSQL instance used
# by the legacy applications.
#
# Key design:
#   * partition key "id": the card identifier (UUID string), used by the
#     worker to update the status by id (idempotent under redelivery);
#   * global secondary index "userId-index" (partition key "userId",
#     projection ALL): turns the per owner listing of the GET endpoint into
#     a single DynamoDB query instead of a full scan.
#
# Every item is stored as a flat map of strings (dates in ISO
# yyyy-mm-ddTHH:MM:SS, UTC 0), so no DynamoDB native types are needed.
# Billing is on demand (PAY_PER_REQUEST): the traffic of this table is
# small and spiky, and the mode avoids any capacity planning.

resource "aws_dynamodb_table" "credit_cards" {
  name         = var.credit_cards_table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "id"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "userId"
    type = "S"
  }

  global_secondary_index {
    name            = "userId-index"
    hash_key        = "userId"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled = true
  }
}
