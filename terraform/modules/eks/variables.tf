variable "cluster_name" {
  description = "El nombre del clúster EKS."
  type        = string
}

variable "k8s_cluster_version" {
  description = "La versión de Kubernetes para el clúster EKS."
  type        = string
}

variable "cluster_endpoint_public_access" {
  description = "Habilita o deshabilita el acceso público al endpoint del clúster EKS."
  type        = bool
  default     = false # Generalmente falso para mayor seguridad, a menos que se necesite.
}

variable "override_vpc_id" {
  description = "ID of the VPC where the EKS cluster is placed. When null, the account's default VPC is discovered via the EC2 API (requires ec2:DescribeVpcs, denied in the current lab account)."
  type        = string
  default     = null #"vpc-02b0985fc383db11c" # Default VPC of the AWS Academy lab account
}

variable "override_subnet_ids" {
  description = "Subnet IDs for the EKS cluster. When null, the subnets of the default VPC are discovered via the EC2 API (requires ec2:DescribeSubnets, denied in the current lab account)."
  type        = list(string)
  default     = null #["subnet-0c27d8a954dd50f43", "subnet-0ce438797e31861ee", "subnet-0fb22cd1b4ffa666d", "subnet-0db3ba6dcd580a4f8"]
}

variable "override_cluster_role_arn" {
  description = "ARN of the IAM role used by the EKS control plane. When null, the role is discovered via the IAM API (requires iam:ListRoles, denied in the current lab account)."
  type        = string
  default     = null #"arn:aws:iam::414547521621:role/c224578a5671942l16381943t1w414547-LabEksClusterRole-AfJWgZVGCPGC"
}

variable "override_node_role_arn" {
  description = "ARN of the IAM role used by the EKS node groups. When null, the role is discovered via the IAM API (requires iam:ListRoles, denied in the current lab account)."
  type        = string
  default     = null #"arn:aws:iam::414547521621:role/c224578a5671942l16381943t1w414547521-LabEksNodeRole-OZ6r09zhTIHc"
}

variable "override_lab_role_arn" {
  description = "ARN of the lab IAM role mapped in aws-auth. When null, the role is discovered via the IAM API (requires iam:ListRoles, denied in the current lab account)."
  type        = string
  default     = null #"arn:aws:iam::414547521621:role/LabRole"
}
