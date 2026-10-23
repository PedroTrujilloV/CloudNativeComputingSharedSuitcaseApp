aws_region               = "us-east-1"
db_publicly_accessible   = true # para pruebas, no recomendado en producción
sg_ingress_cidr_blocks   = ["0.0.0.0/0"] # para pruebas, no recomendado en producción
secret_name              = "grupo33/db-credentials"
db_allocated_storage_gib = 20 # Almacenamiento inicial en GB https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html
db_name                  = "shared_db"
create_app_tables        = true # Crea las 4 tablas compartidas (users, routes, posts, offers, scores) en la BD
owner                    = "pe.trujillo" # Reemplazar con el nombre de usuario real


override_vpc_id            = "<VPC_ID>"
override_subnet_ids        = ["<SUBNET_ID>", "<SUBNET_ID>", "<SUBNET_ID>", "<SUBNET_ID>"]
override_cluster_role_arn  = "<EKS_CLUSTER_ROLE_ARN>"
override_node_role_arn     = "<EKS_NODE_ROLE_ARN>"
override_lab_role_arn      = "<LAB_ROLE_ARN>"