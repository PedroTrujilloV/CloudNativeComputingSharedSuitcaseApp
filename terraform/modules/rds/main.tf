#####################################
# Database Network Configuration
#####################################

resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "rds-default-subnet-group"
  subnet_ids = local.subnet_ids
}

resource "aws_security_group" "rds_sg" {
  name        = "tf-rds-postgres-sg"
  description = "Permitir trafico de entrada a Postgres"
  vpc_id      = local.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.sg_ingress_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "all" # Changed from "-1" to "all" for clarity
    cidr_blocks = ["0.0.0.0/0"]
  }
}

#####################################
# Database Configuration
#####################################

resource "aws_db_instance" "mi_rds_postgres" {
  allocated_storage      = var.db_allocated_storage_gib
  engine                 = "postgres"
  engine_version         = "17.5" # Convierta esta línea a una variable si es necesario
  instance_class         = "db.t3.micro" # Convierta esta línea a una variable si es necesario
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  skip_final_snapshot    = true
  db_subnet_group_name   = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  publicly_accessible    = var.db_publicly_accessible
}

#####################################
# Optional: application tables
#####################################
# When create_app_tables is true, the four tables shared by the users,
# routes, posts and offers apps are created in the same RDS database.
# The SQL is rendered from schema.sql (kept in sync with the apps'
# SQLAlchemy models) and applied with psql via local-exec once the instance
# exists (the trigger references create the implicit dependency). The
# password is passed through the PGPASSWORD environment variable and is
# never written to the rendered script.
locals {
  schema_sql = file("${path.module}/schema.sql")

  render_schema_script = templatefile(
    "${path.module}/init_schema.sh.tpl",
    {
      host              = aws_db_instance.mi_rds_postgres.address
      port              = aws_db_instance.mi_rds_postgres.port
      db_username       = var.db_username
      db_name           = var.db_name
      render_schema_sql = local.schema_sql
    }
  )
}

resource "null_resource" "init_app_tables" {
  count = var.create_app_tables ? 1 : 0

  triggers = {
    # Re-run the schema when the instance endpoint or the schema file changes.
    endpoint = aws_db_instance.mi_rds_postgres.address
    port     = aws_db_instance.mi_rds_postgres.port
    schema   = file("${path.module}/schema.sql")
  }

  provisioner "local-exec" {
    command     = local.render_schema_script
    interpreter = ["/bin/bash", "-c"]

    environment = {
      PGPASSWORD = var.db_password
    }
  }
}

