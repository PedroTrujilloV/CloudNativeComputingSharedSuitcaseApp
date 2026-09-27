output "secret_arn" {
  description = "ARN del secreto de AWS Secrets Manager."
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "secret_name" {
  description = "Nombre del secreto en AWS Secrets Manager (sirve también como secret-id para la aws cli)."
  value       = aws_secretsmanager_secret.db_credentials.name
}