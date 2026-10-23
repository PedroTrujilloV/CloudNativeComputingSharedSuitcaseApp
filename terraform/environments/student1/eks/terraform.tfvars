region = "us-east-1" 
cluster_name = "grupo33-dann-cluster"
k8s_cluster_version = "1.33"

cluster_endpoint_public_access = true
owner = "pe.trujillo"


override_vpc_id            = "<VPC_ID>"   # new account's values
override_subnet_ids        = ["<SUBNET_ID>", "<SUBNET_ID>", "<SUBNET_ID>", "<SUBNET_ID>", "<SUBNET_ID>", "<SUBNET_ID>"]
override_cluster_role_arn  = "<EKS_CLUSTER_ROLE_ARN>"
override_node_role_arn     = "<EKS_NODE_ROLE_ARN>"
override_lab_role_arn      = "<LAB_ROLE_ARN>"