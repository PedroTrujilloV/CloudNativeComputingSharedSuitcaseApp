# NOTE on what this stack deliberately does NOT expose:
#
# The deploy pipeline (ci_entrega2_deploy.yml) merges every output of every
# stack into a single JSON that GitHub Actions treats as a job output.
# GitHub Actions silently discards a job output when it contains the value
# of any environment secret (the pipeline references `toJSON(secrets)`, so
# ALL environment secrets are in scope). That is what broke the old
# `rds_port` / `rds_db_name` outputs: their values ("5432" and "shared_db")
# are exactly the DB_PORT / DB_NAME environment secrets, so the whole
# combined output was dropped and the k8s envsubst step received nothing.
#
# The k8s manifests therefore do NOT read the port and the database name
# from outputs: they use the fixed values shared by every environment
# (see k8s_entrega2/00-secrets.yml). The credentials themselves (user and
# password) are rendered from the step environment that the pipeline
# injects directly from the GitHub environment secrets, and the host comes
# from the safe `rds_address` output below.

output "rds_address" {
  description = "Endpoint de la instancia RDS."
  value       = module.rds.address
}

output "rds_engine" {
  description = "Motor de la base de datos RDS."
  value       = module.rds.engine
}

output "secrets_manager_secret_name" {
  description = "Nombre del secreto de AWS Secrets Manager (sirve como secret-id para la aws cli)."
  value       = module.secrets_manager.secret_name
}

output "create_app_tables" {
  description = "Indica si se crean las tablas de las apps en la BD compartida."
  value       = module.rds.create_app_tables
}

output "app_table_names" {
  description = "Nombres de las tablas de las apps creadas en la BD compartida."
  value       = module.rds.app_table_names
}
