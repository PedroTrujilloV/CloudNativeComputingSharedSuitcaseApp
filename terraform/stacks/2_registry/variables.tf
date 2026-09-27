variable "region" { 
  description = "La región de AWS donde se desplegarán los recursos."
  type        = string
  nullable    = false
}

variable "owner" {
  description = "Dueño de los recursos. Para propósito acadmémico."
  type        = string
  nullable    = false
}

variable "keep_tags_number" {
  description = "Number of tags to keep in the registry"
  type        = number
}

variable "users_repository_name" {
  description = "Name of users_repository"
  type        = string
  nullable    = false
}

variable "posts_repository_name" {
  description = "Name of the posts_repository"
  type        = string
  nullable    = false
}

variable "scores_repository_name" {
  description = "Name of the scores_repository"
  type        = string
  nullable    = false
}
variable "routes_repository_name" {
  description = "Name of the routes_repository"
  type        = string
  nullable    = false
}
variable "offers_repository_name" {
  description = "Name of the offers_repository"
  type        = string
  nullable    = false
}

variable "rf003_repository_name" {
  description = "Name of the rf003_repository"
  type        = string
  nullable    = false
}

variable "rf004_repository_name" {
  description = "Name of the rf004_repository"
  type        = string
  nullable    = false
}

variable "rf005_repository_name" {
  description = "Name of the rf005_repository"
  type        = string
  nullable    = false
}

variable "credit_cards_repository_name" {
  description = "Name of the credit_cards_repository (Entrega 3, RF-006)"
  type        = string
  nullable    = false
}

variable "card_worker_repository_name" {
  description = "Name of the card_worker_repository (Entrega 3, RF-006; container image of the Lambda function)"
  type        = string
  nullable    = false
}

variable "user_verification_callback_repository_name" {
  description = "Name of the user_verification_callback_repository (Entrega 3, RF-007; container image)"
  type        = string
  nullable    = false
}



variable "db_username" {
  description = "Unused in this stack; declared only because the course evaluation workflow always passes it via -var."
  type        = string
  sensitive   = true
  default     = null
}

variable "db_password" {
  description = "Unused in this stack; declared only because the course evaluation workflow always passes it via -var."
  type        = string
  sensitive   = true
  default     = null
}