region = "us-east-1" 
cluster_name = "grupo33-dann-cluster"
k8s_cluster_version = "1.33"

cluster_endpoint_public_access = true
owner = "pe.trujillo"


override_vpc_id            = "vpc-023ae5af9cb43c707"   # new account's values
override_subnet_ids        = ["subnet-03854659c88a8dc53", "subnet-009b28379cd46653b", "subnet-0e5ca973dd542e56a", "subnet-08f61fd632575f67f", "subnet-014b3049d1f595815", "subnet-0f5d7c57b1195f3f8"]
override_cluster_role_arn  = "arn:aws:iam::690275517310:role/c224581a5671947l16452150t1w690275-LabEksClusterRole-y5evNSZEHrZa"
override_node_role_arn     = "arn:aws:iam::690275517310:role/c224581a5671947l16452150t1w690275517-LabEksNodeRole-QcC5ONPZHJ11"
override_lab_role_arn      = "arn:aws:iam::690275517310:role/LabRole"