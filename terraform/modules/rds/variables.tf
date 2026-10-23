# modules/rds/variables.tf
variable "db_allocated_storage_gib" {
  description = "Almacenamiento inicial en GB para la BD en gibibytes"
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

variable "db_publicly_accessible" {
  description = "Indica si la BD debe ser accesible públicamente."
  type        = bool
  default     = false
}

variable "sg_ingress_cidr_blocks" {
  description = "Lista de bloques CIDR blocks que pueden acceder a la instancia RDS PostgreSQL."
  type        = list(string)
}

variable "override_vpc_id" {
  description = "ID of the VPC where the RDS instance is placed. When null, the account's default VPC is discovered via the EC2 API (requires ec2:DescribeVpcs, denied in the current lab account)."
  type        = string
  default     = null #"<VPC_ID>" # Default VPC of the AWS Academy lab account
}

variable "override_subnet_ids" {
  description = "Subnet IDs for the RDS subnet group. When null, the subnets of the default VPC are discovered via the EC2 API (requires ec2:DescribeSubnets, denied in the current lab account)."
  type        = list(string)
  default     = null # ["<SUBNET_ID>", "<SUBNET_ID>", "<SUBNET_ID>", "<SUBNET_ID>"]
}

variable "create_app_tables" {
  description = "Whether to create the shared tables for the apps (users, routes, posts, offers, scores) in the RDS database after the instance is available. When false, only the database itself is provisioned."
  type        = bool
  default     = false
}

variable "app_table_names" {
  description = "Names of the application tables to create in the shared database (informational output; the schema file always contains all four app tables)."
  type        = list(string)
  default     = ["users", "routes", "posts", "offers", "scores"]
}