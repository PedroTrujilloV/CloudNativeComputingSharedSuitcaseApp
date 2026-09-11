aws_region               = "us-east-1"
db_publicly_accessible   = true # para pruebas, no recomendado en producción
sg_ingress_cidr_blocks   = ["0.0.0.0/0"] # para pruebas, no recomendado en producción
secret_name              = "grupo33/db-credentials"
db_allocated_storage_gib = 20 # Almacenamiento inicial en GB https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html
db_name                  = "shared_db"
create_app_tables        = true # Crea las 4 tablas compartidas (users, routes, posts, offers, scores) en la BD
owner                    = "pe.trujillo" # Reemplazar con el nombre de usuario real


override_vpc_id            = "vpc-02b0985fc383db11c"
override_subnet_ids        = ["subnet-0c27d8a954dd50f43", "subnet-0ce438797e31861ee", "subnet-0fb22cd1b4ffa666d", "subnet-0db3ba6dcd580a4f8"]
override_cluster_role_arn  = "arn:aws:iam::414547521621:role/c224578a5671942l16381943t1w414547-LabEksClusterRole-AfJWgZVGCPGC"
override_node_role_arn     = "arn:aws:iam::414547521621:role/c224578a5671942l16381943t1w414547521-LabEksNodeRole-OZ6r09zhTIHc"
override_lab_role_arn      = "arn:aws:iam::414547521621:role/LabRole"