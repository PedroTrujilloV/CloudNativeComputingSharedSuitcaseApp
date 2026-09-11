output "secret_arn" {
  description = "ARN del secreto de AWS Secrets Manager."
  value       = aws_secretsmanager_secret.db_credentials.arn
}