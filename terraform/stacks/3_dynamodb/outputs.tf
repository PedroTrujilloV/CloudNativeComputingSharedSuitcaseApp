output "credit_cards_table_name" {
  description = "Nombre de la tabla DynamoDB de la entidad CreditCard."
  value       = aws_dynamodb_table.credit_cards.name
}

output "credit_cards_table_arn" {
  description = "ARN de la tabla DynamoDB de la entidad CreditCard."
  value       = aws_dynamodb_table.credit_cards.arn
}
