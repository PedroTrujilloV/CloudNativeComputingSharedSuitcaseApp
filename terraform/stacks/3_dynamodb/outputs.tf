# NOTE: the table ARN is deliberately NOT exposed. Its value embeds the AWS
# account id, and the deploy pipeline merges every stack output into a single
# JSON that GitHub Actions silently discards when it contains the value of any
# environment secret (the ACCOUNT_ID environment secret). The ARN can still be
# looked up with the aws cli (aws dynamodb describe-table) when needed.

output "credit_cards_table_name" {
  description = "Nombre de la tabla DynamoDB de la entidad CreditCard (seguro de exponer: no contiene ningun valor de secreto del ambiente)."
  value       = aws_dynamodb_table.credit_cards.name
}
