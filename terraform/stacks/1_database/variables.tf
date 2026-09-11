variable "aws_region" {
  description = "La región de AWS donde se desplegarán los recursos."
  type        = string
}

variable "db_publicly_accessible" {
  description = "Indica si la BD debe ser accesible públicamente."
  type        = bool
}

variable "sg_ingress_cidr_blocks" {
  description = "Lista de bloques CIDR permitidos para acceder a la instancia RDS PostgreSQL."
  type        = list(string)
}

variable "secret_name" {
  description = "Nombre del secreto en AWS Secrets Manager."
  type        = string
}

variable "db_allocated_storage_gib" {
  description = "Almacenamiento inicial en GB para la BD en gibibytes."
  type        = number
}

variable "db_name" {
  description = "Nombre de la base de datos en RDS."
  type        = string
}

variable "db_username" {
  description = "Usuario administrador para la base de datos RDS."
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Contraseña para el usuario administrador de la base de datos RDS."
  type        = string
  sensitive   = true
}

variable "create_app_tables" {
  description = "Indica si se deben crear las tablas compartidas de las apps (users, routes, posts, offers, scores) en la base de datos RDS."
  type        = bool
  default     = false
}

variable "app_table_names" {
  description = "Nombres de las tablas de las apps que se crean en la BD compartida."
  type        = list(string)
  default     = ["users", "routes", "posts", "offers", "scores"]
}

variable "owner" {
  description = "Propietario de los recursos, generalmente el nombre del usuario o equipo."
  type        = string
}