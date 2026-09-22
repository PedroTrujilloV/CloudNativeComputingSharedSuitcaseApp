variable "aws_region" {
  description = "La región de AWS donde se desplegarán los recursos."
  type        = string
}

variable "owner" {
  description = "Propietario de los recursos, generalmente el nombre del usuario o equipo."
  type        = string
}

variable "card_verification_topic_name" {
  description = "Nombre del topic SNS que recibe el resultado de la verificación de tarjetas de crédito (RF-006)."
  type        = string
}

variable "user_verification_topic_name" {
  description = "Nombre del topic SNS que recibe el resultado de la verificación de identidad de usuarios (RF-007)."
  type        = string
}
