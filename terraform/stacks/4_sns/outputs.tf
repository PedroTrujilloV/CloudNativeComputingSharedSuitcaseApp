# NOTE on what this stack deliberately does NOT expose:
#
# The deploy pipeline merges every output of every stack into a single JSON
# that GitHub Actions treats as a job output, and it silently discards the
# output when it contains the value of any environment secret. The topic
# ARNs embed the AWS account id (the ACCOUNT_ID environment secret), so they
# are NOT exposed: the k8s manifest (k8s_entrega2/28-user-verification-
# callback.yml) reconstructs the ARN from the safe topic name plus
# $AWS_REGION and $ACCOUNT_ID (both provided by the pipeline itself).
# Likewise `email_endpoint` is not exposed (it equals the EMAIL_TO_NOTIFY
# environment secret); the email subscriptions still use that value
# internally (locals.tf, never an output). The ARNs remain available via
# `aws sns list-topics` for operations.

output "card_verification_topic_name" {
  description = "Nombre del topic SNS de verificacion de tarjetas de credito (RF-006). Seguro de exponer: no contiene ningun valor de secreto del ambiente."
  value       = aws_sns_topic.card_verification.name
}

output "user_verification_topic_name" {
  description = "Nombre del topic SNS de verificacion de identidad de usuarios (RF-007). El manifiesto del callback reconstruye el ARN completo a partir de este nombre."
  value       = aws_sns_topic.user_verification.name
}
