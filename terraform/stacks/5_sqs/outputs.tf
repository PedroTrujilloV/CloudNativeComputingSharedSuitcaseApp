output "card_verification_queue_url" {
  description = "URL de la cola de eventos de verificación de tarjetas (consumida por el manifiesto de credit_cards_app vía envsubst)."
  value       = aws_sqs_queue.card_verification.url
}

output "card_verification_queue_arn" {
  description = "ARN de la cola de eventos de verificación de tarjetas."
  value       = aws_sqs_queue.card_verification.arn
}

output "card_dead_letter_queue_url" {
  description = "URL de la dead letter queue de la cola de verificación (operación: inspección de eventos que agotaron los reintentos)."
  value       = aws_sqs_queue.card_verification_dead_letter.url
}

output "card_dead_letter_queue_arn" {
  description = "ARN de la dead letter queue de la cola de verificación."
  value       = aws_sqs_queue.card_verification_dead_letter.arn
}
