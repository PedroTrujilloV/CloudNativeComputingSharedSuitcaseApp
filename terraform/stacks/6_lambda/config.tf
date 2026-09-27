# stack/app/config.tf
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      "terraform" : true,
      "owner" : var.owner
    }
  }
}

terraform {
  required_providers {
    # Pinned to the same major as every other stack. The aws_elb data
    # source in data.tf is used with a tags-only lookup (the ingress
    # balancer name is not known at plan time); in provider v6 the
    # data source's "name" argument became required, so a tags-only
    # lookup no longer validates under v6.
    aws = {
      source  = "hashicorp/aws"
      # version = "~> 5"
    }
  }
}
