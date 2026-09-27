resource "random_id" "secret_suffix" {
  byte_length = 4

  keepers = {
    name_prefix = var.secret_name
  }
}

# Agregamos un sufijo aleatorio al nombre del secreto para evitar colisiones
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.secret_name}${random_id.secret_suffix.hex}"
  description = "Secret for RDS database credentials including connection details"
}

resource "aws_secretsmanager_secret_version" "db_credentials_version" {
  secret_id     = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username,
    password = var.db_password,
    engine   = var.db_engine,
    host     = var.db_host,
    port     = var.db_port,
    dbname   = var.db_name
  })
}