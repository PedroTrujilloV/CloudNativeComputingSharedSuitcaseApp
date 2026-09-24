variable "aws_region" {
  description = "La región de AWS donde se desplegarán los recursos."
  type        = string
  nullable    = false
}

variable "owner" {
  description = "Dueño de los recursos. Para propósito académico."
  type        = string
  nullable    = false
}

variable "queue_name" {
  description = "Nombre de la cola de eventos de verificación de tarjetas."
  type        = string
  nullable    = false
}

variable "dead_letter_queue_name" {
  description = "Nombre de la dead letter queue de la cola de verificación."
  type        = string
  nullable    = false
}

variable "max_receive_count" {
  description = "Número de recepciones fallidas antes de mover el evento a la dead letter queue."
  type        = number
}

variable "visibility_timeout_seconds" {
  description = "Timeout de visibilidad de la cola; debe ser mayor que la invocación peor caso del worker."
  type        = number
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
