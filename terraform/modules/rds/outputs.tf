output "address" {
  description = "Endpoint de la instancia RDS."
  value       = aws_db_instance.mi_rds_postgres.address
}

output "port" {
  description = "Puerto de la instancia RDS."
  value       = aws_db_instance.mi_rds_postgres.port
}

output "engine" {
  description = "Motor de la base de datos RDS."
  value       = aws_db_instance.mi_rds_postgres.engine
}

output "db_name" { # Esto es el nombre de la BD interna, un output válido
  description = "Nombre de la instancia de base de datos RDS."
  value       = aws_db_instance.mi_rds_postgres.db_name
}

output "create_app_tables" {
  description = "Indica si se crean las tablas de las apps (users, routes, posts, offers) en la BD compartida."
  value       = var.create_app_tables
}

output "app_table_names" {
  description = "Nombres de las tablas de las apps creadas en la BD compartida (vacío cuando create_app_tables es false)."
  value       = var.create_app_tables ? var.app_table_names : []
}