output "card_worker_function_name" {
  description = "Nombre de la función Lambda del worker de verificación de tarjetas."
  value       = aws_lambda_function.card_worker.function_name
}

output "card_worker_function_arn" {
  description = "ARN de la función Lambda del worker de verificación de tarjetas."
  value       = aws_lambda_function.card_worker.arn
}
