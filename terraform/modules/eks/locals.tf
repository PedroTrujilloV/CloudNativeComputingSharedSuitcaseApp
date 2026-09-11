locals {
  cluster_role_arn = var.override_cluster_role_arn != null ? var.override_cluster_role_arn : tolist(data.aws_iam_roles.eks_cluster[0].arns)[0]
  node_role_arn    = var.override_node_role_arn != null ? var.override_node_role_arn : tolist(data.aws_iam_roles.eks_node[0].arns)[0]
  lab_role_arn     = var.override_lab_role_arn != null ? var.override_lab_role_arn : tolist(data.aws_iam_roles.lab_role[0].arns)[0]

  vpc_id     = var.override_vpc_id != null ? var.override_vpc_id : data.aws_vpc.default[0].id
  subnet_ids = var.override_subnet_ids != null ? var.override_subnet_ids : data.aws_subnets.all[0].ids
}