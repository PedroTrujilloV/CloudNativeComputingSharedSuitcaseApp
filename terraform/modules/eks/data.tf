# The AWS Academy lab account denies the EC2 and IAM read APIs
# (ec2:DescribeVpcs, ec2:DescribeSubnets, iam:ListRoles) via the
# voc-cancel-cred policy, so the default VPC, subnets and lab IAM roles are
# provided through variable defaults (see variables.tf). The data sources
# below only run when an override is set to null, i.e. in environments with
# full API access.
data "aws_vpc" "default" {
  count   = var.override_vpc_id == null ? 1 : 0
  default = true
}

data "aws_subnets" "all" {
  count   = var.override_subnet_ids == null ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
  filter {
    name   = "availability-zone"
    values = ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d"]
  }
}

data "aws_iam_roles" "eks_cluster" {
  count      = var.override_cluster_role_arn == null ? 1 : 0
  name_regex = "LabEksClusterRole"
}

data "aws_iam_roles" "eks_node" {
  count      = var.override_node_role_arn == null ? 1 : 0
  name_regex = "LabEksNodeRole"
}

data "aws_iam_roles" "lab_role" {
  count      = var.override_lab_role_arn == null ? 1 : 0
  name_regex = "LabRole"
}