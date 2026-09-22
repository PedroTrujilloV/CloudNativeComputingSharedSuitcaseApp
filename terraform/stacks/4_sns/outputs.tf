output "card_verification_topic_arn" {
  description = "ARN del topic SNS de verificación de tarjetas de crédito (RF-006)."
  value       = aws_sns_topic.card_verification.arn
}

output "user_verification_topic_arn" {
  description = "ARN del topic SNS de verificación de identidad de usuarios (RF-007)."
  value       = aws_sns_topic.user_verification.arn
}

output "email_endpoint" {
  description = "Dirección de correo de las suscripciones. Proviene de la clave EMAIL_TO_NOTIFY del secret 'secrets-pipeline-native-map' de AWS Secrets Manager, poblado por el pipeline desde los secrets del ambiente de GitHub. Nunca se hardcodea en este repositorio."
  value       = local.email_to_notify
  sensitive   = true
}
