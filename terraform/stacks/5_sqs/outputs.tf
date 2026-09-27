# NOTE on what this stack deliberately does NOT expose:
#
# The deploy pipeline merges every output of every stack into a single JSON
# that GitHub Actions treats as a job output, and it silently discards the
# output when it contains the value of any environment secret. Every SQS
# URL/ARN embeds the AWS account id (the ACCOUNT_ID environment secret), so
# none of them is exposed: the k8s manifest
# (k8s_entrega3/k8s-credit-cards-deployment.yml) reconstructs the queue URL
# from the safe queue name plus $AWS_REGION and $ACCOUNT_ID (both provided
# by the pipeline itself). The URLs remain available via
# `aws sqs list-queues` for operations.

output "card_verification_queue_name" {
  description = "Nombre de la cola de eventos de verificacion de tarjetas (RF-006). El manifiesto de credit_cards_app reconstruye la URL completa a partir de este nombre."
  value       = aws_sqs_queue.card_verification.name
}
