variable "secret_name" {
  description = "Nombre del secreto en AWS Secrets Manager."
  type        = string
}

variable "db_username" {
  description = "Usuario de la base de datos."
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Contraseña de la base de datos."
  type        = string
  sensitive   = true
}

variable "db_engine" {
  description = "Motor de la base de datos."
  type        = string
}

variable "db_host" {
  description = "Host (endpoint) de la base de datos."
  type        = string
}

variable "db_port" {
  description = "Puerto de la base de datos."
  type        = number
}

variable "db_name" {
  description = "Nombre de la base de datos."
  type        = string
}
