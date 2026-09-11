module "rds" {
  source                 = "../../modules/rds"
  db_allocated_storage_gib   = var.db_allocated_storage_gib
  db_name                    = var.db_name
  db_username                = var.db_username
  db_password                = var.db_password
  db_publicly_accessible     = var.db_publicly_accessible
  sg_ingress_cidr_blocks     = var.sg_ingress_cidr_blocks
  create_app_tables          = var.create_app_tables
  app_table_names            = var.app_table_names
}

module "secrets_manager" {
  source      = "../../modules/secrets_manager"
  secret_name = var.secret_name
  db_username = var.db_username     # Mismo usuario que se usa para RDS
  db_password = var.db_password     # Misma contraseña que se usa para RDS
  db_engine   = module.rds.engine   # RDS engine type, e.g., "postgres"
  db_host     = module.rds.address  # RDS host address
  db_port     = module.rds.port     # RDS host port, e.g., "5432"
  db_name     = module.rds.db_name  # RDS database name

  # Explicit dependency to ensure RDS is fully created before Secrets Manager tries to read its outputs
  depends_on = [
    module.rds
  ]
}

