output "rds_address" {
  description = "Endpoint de la instancia RDS."
  value       = module.rds.address
}

output "rds_port" {
  description = "Puerto de la instancia RDS."
  value       = module.rds.port
}

output "rds_engine" {
  description = "Motor de la base de datos RDS."
  value       = module.rds.engine
}

output "rds_db_name" {
  description = "Nombre de la base de datos RDS."
  value       = module.rds.db_name
}

output "secrets_manager_secret_arn" {
  description = "ARN del secreto de AWS Secrets Manager."
  value       = module.secrets_manager.secret_arn
}

output "create_app_tables" {
  description = "Indica si se crean las tablas de las apps en la BD compartida."
  value       = module.rds.create_app_tables
}

output "app_table_names" {
  description = "Nombres de las tablas de las apps creadas en la BD compartida."
  value       = module.rds.app_table_names
}
