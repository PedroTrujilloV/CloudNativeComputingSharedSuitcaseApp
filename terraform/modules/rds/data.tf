# The AWS Academy lab account denies the EC2 read APIs (ec2:DescribeVpcs /
# ec2:DescribeSubnets) via the voc-cancel-cred policy, so the default VPC and
# subnets are provided through variable defaults (see variables.tf). The data
# sources below only run when an override is set to null, i.e. in
# environments with full API access.
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

locals {
  vpc_id     = var.override_vpc_id != null ? var.override_vpc_id : data.aws_vpc.default[0].id
  subnet_ids = var.override_subnet_ids != null ? var.override_subnet_ids : data.aws_subnets.all[0].ids
}