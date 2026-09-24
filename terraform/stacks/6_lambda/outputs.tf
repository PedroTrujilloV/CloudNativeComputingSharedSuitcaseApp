output "card_worker_function_name" {
  description = "Nombre de la función Lambda del worker de verificación de tarjetas."
  value       = aws_lambda_function.card_worker.function_name
}

output "card_worker_function_arn" {
  description = "ARN de la función Lambda del worker de verificación de tarjetas."
  value       = aws_lambda_function.card_worker.arn
}

output "card_worker_role_arn" {
  description = "ARN del rol IAM de ejecución del worker (permiso mínimo)."
  value       = aws_iam_role.card_worker.arn
}

output "card_worker_truenative_url" {
  description = "URL base con la que el worker alcanza TrueNative (host del load balancer de ingress-nginx)."
  value       = local.truenative_url
}
