# SNS email notification topics for the two requirements of Entrega 3.
#
# One topic per requirement, so each producer (the card worker for RF-006
# and the user verification callback for RF-007) publishes to the topic
# that matches its own result, and each topic has a single email
# subscription whose endpoint is the EMAIL_TO_NOTIFY value read from the
# secrets-pipeline-native-map secret (see locals.tf).
#
# While a subscription is in the "pending" state, SNS discards the
# messages: after the deploy, the confirmation email that SNS sends to the
# address must be opened and the link clicked once (manual step,
# documented in the README).

resource "aws_sns_topic" "card_verification" {
  name = var.card_verification_topic_name
}

resource "aws_sns_topic" "user_verification" {
  name = var.user_verification_topic_name
}

resource "aws_sns_topic_subscription" "card_verification_email" {
  topic_arn = aws_sns_topic.card_verification.arn
  protocol  = "email"
  endpoint  = local.email_to_notify
}

resource "aws_sns_topic_subscription" "user_verification_email" {
  topic_arn = aws_sns_topic.user_verification.arn
  protocol  = "email"
  endpoint  = local.email_to_notify
}
