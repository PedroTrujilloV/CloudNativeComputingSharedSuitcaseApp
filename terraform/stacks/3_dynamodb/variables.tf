variable "aws_region" {
  description = "La región de AWS donde se desplegarán los recursos."
  type        = string
}

variable "owner" {
  description = "Propietario de los recursos, generalmente el nombre del usuario o equipo."
  type        = string
}

variable "credit_cards_table_name" {
  description = "Nombre de la tabla DynamoDB de la entidad CreditCard (exclusiva de credit_cards_app)."
  type        = string
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