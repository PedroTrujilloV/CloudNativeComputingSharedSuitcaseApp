aws_region               = "us-east-1"
db_publicly_accessible   = true # para pruebas, no recomendado en producción
sg_ingress_cidr_blocks   = ["0.0.0.0/0"] # para pruebas, no recomendado en producción
secret_name              = "grupo33/db-credentials"
db_allocated_storage_gib = 20 # Almacenamiento inicial en GB https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html
db_name                  = "shared_db"
create_app_tables        = true # Crea las 4 tablas compartidas (users, routes, posts, offers) en la BD
owner                    = "pe.trujillo" # Reemplazar con el nombre de usuario real


override_vpc_id            = "vpc-023ae5af9cb43c707"   # new account's values
override_subnet_ids        = ["subnet-03854659c88a8dc53", "subnet-009b28379cd46653b", "subnet-0e5ca973dd542e56a", "subnet-08f61fd632575f67f", "subnet-014b3049d1f595815", "subnet-0f5d7c57b1195f3f8"]
override_cluster_role_arn  = "arn:aws:iam::690275517310:role/c224581a5671947l16452150t1w690275-LabEksClusterRole-y5evNSZEHrZa"
override_node_role_arn     = "arn:aws:iam::690275517310:role/c224581a5671947l16452150t1w690275517-LabEksNodeRole-QcC5ONPZHJ11"
override_lab_role_arn      = "arn:aws:iam::690275517310:role/LabRole"